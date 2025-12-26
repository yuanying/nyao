"""エージェント基盤

strands-agentsをラップしたNyaoAgentクラスを提供します。
"""

import asyncio
from typing import Any

from strands import Agent
from strands.models.litellm import LiteLLMModel

from nyao.config.settings import LiteLLMSettings
from nyao.core.exceptions import LLMAPIError
from nyao.core.logging import get_logger
from nyao.core.models import LLMResponse
from nyao.utils.retry import retry_async

logger = get_logger(__name__)


class _NonRetryableError(Exception):
    """リトライ不可能なエラーを示す内部例外

    retry_asyncでリトライされないようにするためのラッパー例外。
    skip_retryフラグでリトライをスキップすることを示す。
    """

    def __init__(self, llm_error: LLMAPIError) -> None:
        # retry_asyncでリトライをスキップさせるためのフラグ
        self.skip_retry: bool = True
        self.llm_error = llm_error
        super().__init__()


class NyaoAgent:
    """Nyaoのエージェント基盤クラス

    strands-agentsのAgentをラップし、以下の機能を提供:
    - LiteLLMSettings経由での初期化
    - 自動リトライ（最大3回）
    - 構造化ログ
    - エラーハンドリング（LLMAPIError）
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF = 2.0

    def __init__(
        self,
        settings: LiteLLMSettings,
        system_prompt: str | None = None,
    ) -> None:
        """NyaoAgentを初期化

        Args:
            settings: LiteLLM設定（model_id, client_args, params）
            system_prompt: システムプロンプト（オプション）
        """
        self._settings = settings
        self._system_prompt = system_prompt
        self._model = self._create_model()
        self._agent = Agent(model=self._model, system_prompt=system_prompt)

        logger.info(
            "nyao_agent_initialized",
            model_id=settings.model_id,
            has_system_prompt=system_prompt is not None,
        )

    def _create_model(self) -> LiteLLMModel:
        """LiteLLMSettingsからLiteLLMModelを作成

        Returns:
            LiteLLMModel: 設定済みのLiteLLMModelインスタンス
        """
        return LiteLLMModel(
            model_id=self._settings.model_id,
            client_args=self._settings.client_args,
            params=self._settings.params,
        )

    async def call_llm(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """LLMを呼び出してレスポンスを取得

        Args:
            prompt: ユーザープロンプト文字列
            temperature: 温度パラメータ（Noneの場合は設定のデフォルト）
            max_tokens: 最大トークン数（Noneの場合は設定のデフォルト）

        Returns:
            LLMResponse: LLMからのレスポンス

        Raises:
            LLMAPIError: API呼び出しエラー時
        """
        logger.debug(
            "call_llm_start",
            prompt_length=len(prompt),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # temperature/max_tokensが指定されていれば設定を更新
        if temperature is not None or max_tokens is not None:
            config_update: dict[str, Any] = {}
            if temperature is not None:
                config_update["temperature"] = temperature
            if max_tokens is not None:
                config_update["max_tokens"] = max_tokens
            self._model.update_config(**config_update)

        try:
            # リトライ付きでLLM呼び出し
            result = await self._call_with_retry(prompt)

            # AgentResultをLLMResponseに変換
            content = self._extract_content(result)
            response = LLMResponse(
                content=content,
                model=self._settings.model_id,
                usage={},  # strands.AgentはUsage情報を提供しないため空辞書
                finish_reason=result.stop_reason or "unknown",
            )

            logger.debug(
                "call_llm_success",
                content_length=len(content),
                finish_reason=response.finish_reason,
            )

            return response

        except LLMAPIError:
            # 既にLLMAPIErrorの場合はそのまま再送出
            raise
        except Exception as e:
            # その他の例外をLLMAPIErrorに変換
            status_code = getattr(e, "status_code", None)
            logger.error(
                "call_llm_error",
                error=str(e),
                model=self._settings.model_id,
                status_code=status_code,
            )
            raise LLMAPIError(
                message=str(e),
                model=self._settings.model_id,
                status_code=status_code,
            ) from e

    async def _call_with_retry(self, prompt: str) -> Any:
        """リトライ付きでAgent.__call__を呼び出す

        Args:
            prompt: ユーザープロンプト

        Returns:
            AgentResult: Agentからのレスポンス

        Raises:
            LLMAPIError: リトライ不可能なエラーの場合
            Exception: リトライ可能なエラーで最大リトライ回数を超えた場合
        """

        async def call_agent() -> Any:
            try:
                # 同期的なAgent.__call__を非同期化
                return await asyncio.to_thread(self._agent, prompt)
            except Exception as e:
                # ステータスコードを確認してリトライ可能か判定
                status_code = getattr(e, "status_code", None)
                if status_code is not None and not self._is_retryable_status(status_code):
                    # リトライ不可能なエラーは_NonRetryableErrorでラップ
                    llm_error = LLMAPIError(
                        message=str(e),
                        model=self._settings.model_id,
                        status_code=status_code,
                    )
                    raise _NonRetryableError(llm_error) from e
                raise

        try:
            return await retry_async(
                call_agent,
                max_retries=self.MAX_RETRIES,
                delay=self.RETRY_DELAY,
                backoff=self.RETRY_BACKOFF,
                exceptions=(Exception,),
                skip_on=lambda e: getattr(e, "skip_retry", False),
            )
        except _NonRetryableError as e:
            # リトライ不可能なエラーは元のLLMAPIErrorをスロー
            raise e.llm_error from e

    def _is_retryable_status(self, status_code: int) -> bool:
        """ステータスコードがリトライ可能かどうかを判定

        Args:
            status_code: HTTPステータスコード

        Returns:
            リトライ可能な場合True
        """
        return status_code in LLMAPIError.RETRYABLE_STATUS_CODES

    def _extract_content(self, result: Any) -> str:
        """AgentResultからコンテンツを抽出

        Args:
            result: Agentからのレスポンス

        Returns:
            抽出されたテキストコンテンツ
        """
        message = result.message
        if isinstance(message, dict) and "content" in message:
            content_list = message["content"]
            if content_list and isinstance(content_list, list):
                first_content = content_list[0]
                if isinstance(first_content, dict) and "text" in first_content:
                    return first_content["text"]
        return ""
