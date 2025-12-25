"""LLM呼び出しラッパー

プロンプト管理とLLM接続を組み合わせ、高レベルなLLM呼び出しインターフェースを提供します。
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, cast

from nyao.core.exceptions import LLMAPIError
from nyao.core.logging import get_logger
from nyao.core.models import LLMResponse, ResponseDecision
from nyao.integrations.llm.agent_base import NyaoAgent
from nyao.integrations.llm.prompts import PromptManager
from nyao.utils.retry import retry_async

if TYPE_CHECKING:
    from nyao.config.settings import Settings
    from nyao.core.models import ConversationContext, SlackMessage

logger = get_logger(__name__)


class _RetryableLLMAPIError(LLMAPIError):
    """リトライ可能なLLMAPIErrorをラップするクラス

    generate_response内でリトライ対象を区別するために使用される内部クラス。
    """

    pass


class LLMCaller:
    """LLM呼び出しの高レベルAPI

    プロンプト管理とLLM呼び出しを統合し、
    応答判定・応答生成のための使いやすいインターフェースを提供する。
    """

    # 応答判定のパラメータ（一貫性重視）
    JUDGE_TEMPERATURE = 0.3
    JUDGE_MAX_TOKENS = 200

    # 応答生成のパラメータ（多様性重視）
    GENERATE_TEMPERATURE = 0.8
    GENERATE_MAX_TOKENS = 300

    # リトライ設定
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF = 2.0

    def __init__(
        self,
        agent: NyaoAgent,
        prompt_manager: PromptManager,
    ) -> None:
        """初期化

        Args:
            agent: NyaoAgentインスタンス
            prompt_manager: PromptManagerインスタンス
        """
        self.agent = agent
        self.prompt_manager = prompt_manager

    async def judge_should_respond(
        self,
        message: SlackMessage,
        elapsed_seconds: int,
        reaction_count: int,
        reply_count: int,
    ) -> ResponseDecision:
        """応答すべきかどうかを判定

        Args:
            message: 対象のSlackメッセージ
            elapsed_seconds: メッセージ投稿からの経過秒数
            reaction_count: リアクション数
            reply_count: 返信数

        Returns:
            ResponseDecision: 応答判定結果

        Note:
            エラー時は安全側に倒し、should_respond=Falseを返す
        """
        try:
            # プロンプトを構築
            messages = self.prompt_manager.build_should_respond_prompt(
                message=message,
                elapsed_seconds=elapsed_seconds,
                reaction_count=reaction_count,
                reply_count=reply_count,
            )

            # LLMを呼び出し
            response = self.agent.call_llm(
                messages=messages,
                temperature=self.JUDGE_TEMPERATURE,
                max_tokens=self.JUDGE_MAX_TOKENS,
            )

            # JSONレスポンスをパース
            result = self._parse_json_response(response.content)

            # ResponseDecisionを生成
            return ResponseDecision(
                should_respond=result.get("should_respond", False),
                reason=result.get("reason", ""),
                confidence=result.get("confidence", 0.0),
                suggested_delay_minutes=result.get("suggested_delay_minutes"),
            )

        except (LLMAPIError, ValueError, KeyError) as e:
            # エラー時は安全側に倒す
            logger.warning(
                "judge_should_respond_fallback",
                error=str(e),
                message_id=message.message_id,
            )
            return ResponseDecision(
                should_respond=False,
                reason=f"LLM API error: {e!s}",
                confidence=0.0,
            )

    async def generate_response(
        self,
        message: SlackMessage,
        context: ConversationContext | None = None,
    ) -> LLMResponse:
        """応答メッセージを生成

        Args:
            message: 返信対象のSlackメッセージ
            context: 会話コンテキスト（オプション）

        Returns:
            LLMResponse: 生成された応答

        Raises:
            LLMAPIError: 応答生成に失敗した場合
        """

        async def _generate() -> LLMResponse:
            try:
                # プロンプトを構築
                messages = self.prompt_manager.build_response_generation_prompt(
                    message=message,
                    context=context,
                )

                # LLMを呼び出し
                return self.agent.call_llm(
                    messages=messages,
                    temperature=self.GENERATE_TEMPERATURE,
                    max_tokens=self.GENERATE_MAX_TOKENS,
                )
            except LLMAPIError as e:
                # リトライ可能なエラーの場合のみラップして再送出
                if e.is_retryable():
                    raise _RetryableLLMAPIError(
                        message=str(e),
                        model=e.model,
                        status_code=e.status_code,
                    ) from e
                # リトライ不可能なエラーはそのまま再送出
                raise

        try:
            return cast(
                LLMResponse,
                await retry_async(
                    _generate,
                    max_retries=self.MAX_RETRIES,
                    delay=self.RETRY_DELAY,
                    backoff=self.RETRY_BACKOFF,
                    exceptions=(_RetryableLLMAPIError,),
                ),
            )
        except _RetryableLLMAPIError as e:
            # リトライ回数を使い果たした場合、元のLLMAPIErrorとして再送出
            raise LLMAPIError(
                message=str(e),
                model=e.model,
                status_code=e.status_code,
            ) from e.__cause__

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """LLMのJSON形式レスポンスをパース

        Args:
            content: LLMからの応答テキスト

        Returns:
            パースされた辞書

        Raises:
            ValueError: JSONパースに失敗した場合
        """
        # マークダウンのコードブロックを除去
        # ```json ... ``` または ``` ... ``` パターンに対応
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(code_block_pattern, content)

        if match:
            json_str = match.group(1)
        else:
            json_str = content

        try:
            stripped_json = json_str.strip()
            return json.loads(stripped_json)
        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_failed",
                content=content[:200],
                error=str(e),
            )
            preview = stripped_json[:200]
            raise ValueError(
                f"Failed to parse JSON response: {e}. Content preview: {preview!r}"
            ) from e

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMCaller:
        """設定からLLMCallerを生成するファクトリメソッド

        Args:
            settings: アプリケーション設定

        Returns:
            設定に基づいて初期化されたLLMCaller
        """
        agent = NyaoAgent.from_settings(settings)
        prompt_manager = PromptManager.from_settings(settings)

        return cls(agent=agent, prompt_manager=prompt_manager)
