"""エージェント基盤

strands-agentsを使用したLLMエージェント基盤を提供します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from strands import Agent
from strands.models.litellm import LiteLLMModel

from nyao.core.exceptions import LLMAPIError
from nyao.core.logging import get_logger
from nyao.core.models import LLMResponse

if TYPE_CHECKING:
    from nyao.config.settings import Settings

logger = get_logger(__name__)


class NyaoAgent(Agent):
    """Nyao用のLLMエージェント基盤クラス

    strands-agentsのAgentを継承し、LiteLLMModelを使用してLLM APIを呼び出す。
    """

    def __init__(
        self,
        model_id: str,
        api_key: str | None = None,
        api_base: str | None = None,
        default_params: dict[str, Any] | None = None,
    ) -> None:
        """初期化

        Args:
            model_id: LiteLLM形式のモデルID (例: "openai/gpt-4o", "anthropic/claude-3-5-sonnet")
            api_key: APIキー（Noneの場合は環境変数から取得）
            api_base: カスタムAPIエンドポイント（オプション）
            default_params: デフォルトのモデルパラメータ
        """
        self.model_id = model_id
        self.api_key = api_key
        self.api_base = api_base
        self.default_params = default_params or {}

        # LiteLLMModelを初期化
        client_args: dict[str, Any] = {}
        if api_key:
            client_args["api_key"] = api_key
        if api_base:
            client_args["api_base"] = api_base

        model = LiteLLMModel(
            model_id=model_id,
            client_args=client_args if client_args else None,
        )

        # 親クラスの初期化
        super().__init__(model=model)

    def call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """LLMを呼び出す

        Args:
            messages: OpenAI形式のメッセージリスト
            temperature: 生成の多様性パラメータ
            max_tokens: 最大トークン数

        Returns:
            LLMResponse: LLM応答データ

        Raises:
            LLMAPIError: API呼び出しに失敗した場合
        """
        try:
            # メッセージをプロンプト文字列に変換
            prompt = self._messages_to_prompt(messages)

            # エージェントを呼び出し
            response = self._invoke_agent(prompt, temperature, max_tokens)

            # レスポンスをLLMResponseに変換
            return self._convert_response(response)

        except LLMAPIError:
            # 既にLLMAPIErrorの場合はそのまま再送出
            raise
        except Exception as e:
            # ステータスコードを取得（可能な場合）
            status_code = getattr(e, "status_code", None)

            logger.error(
                "llm_call_failed",
                model=self.model_id,
                error=str(e),
                status_code=status_code,
            )

            raise LLMAPIError(
                message=str(e),
                model=self.model_id,
                status_code=status_code,
            ) from e

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """OpenAI形式のメッセージをプロンプト文字列に変換

        Args:
            messages: OpenAI形式のメッセージリスト

        Returns:
            プロンプト文字列
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(content)
            elif role == "user":
                parts.append(content)
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        return "\n\n".join(parts)

    def _invoke_agent(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Any:
        """エージェントを呼び出す（テスト用にオーバーライド可能）

        Args:
            prompt: プロンプト文字列
            temperature: 生成の多様性パラメータ
            max_tokens: 最大トークン数

        Returns:
            エージェントのレスポンス
        """
        # strands Agentの__call__を使用
        return self(prompt)

    def _convert_response(self, response: Any) -> LLMResponse:
        """エージェントのレスポンスをLLMResponseに変換

        Args:
            response: エージェントのレスポンス

        Returns:
            LLMResponse
        """
        # strands Agentのレスポンス構造に応じて変換
        if hasattr(response, "message") and hasattr(response.message, "content"):
            # content は ContentBlock のリスト
            content_blocks = response.message.content
            if content_blocks and hasattr(content_blocks[0], "text"):
                content = content_blocks[0].text
            else:
                content = str(content_blocks)
        else:
            content = str(response)

        # メトリクス情報を取得
        usage = {}
        if hasattr(response, "metrics"):
            metrics = response.metrics
            if hasattr(metrics, "inputTokens"):
                usage["prompt_tokens"] = metrics.inputTokens
            if hasattr(metrics, "outputTokens"):
                usage["completion_tokens"] = metrics.outputTokens
            usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get(
                "completion_tokens", 0
            )

        # 終了理由を取得
        finish_reason = "stop"
        if hasattr(response, "stop_reason"):
            finish_reason = response.stop_reason or "stop"

        return LLMResponse(
            content=content,
            model=self.model_id,
            usage=usage,
            finish_reason=finish_reason,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> NyaoAgent:
        """設定からNyaoAgentを生成するファクトリメソッド

        Args:
            settings: アプリケーション設定

        Returns:
            設定に基づいて初期化されたNyaoAgent
        """
        litellm_config = settings.litellm

        model_id = litellm_config.get("model_id", "openai/gpt-4o")
        api_key = litellm_config.get("api_key")
        api_base = litellm_config.get("api_base")
        params = litellm_config.get("params", {})

        return cls(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            default_params=params,
        )
