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
        client_args: dict[str, Any] | None = None,
        default_params: dict[str, Any] | None = None,
    ) -> None:
        """初期化

        Args:
            model_id: LiteLLM形式のモデルID (例: "openai/gpt-4o", "anthropic/claude-3-5-sonnet")
            client_args: LiteLLMクライアント引数（api_key, api_base等）
            default_params: デフォルトのモデルパラメータ（temperature, max_tokens等）
        """
        self.model_id = model_id
        self.client_args = client_args or {}
        self.default_params = default_params or {}

        # LiteLLMModelを初期化
        model = LiteLLMModel(
            model_id=model_id,
            client_args=client_args if client_args else None,
        )

        # 親クラスの初期化
        super().__init__(model=model)

    def call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """LLMを呼び出す

        Args:
            messages: OpenAI形式のメッセージリスト
            temperature: 生成の多様性パラメータ（Noneの場合はdefault_paramsを使用）
            max_tokens: 最大トークン数（Noneの場合はdefault_paramsを使用）

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
        temperature: float | None,
        max_tokens: int | None,
    ) -> Any:
        """エージェントを呼び出す（テスト用にオーバーライド可能）

        Args:
            prompt: プロンプト文字列
            temperature: 生成の多様性パラメータ（Noneの場合はdefault_paramsを使用）
            max_tokens: 最大トークン数（Noneの場合はdefault_paramsを使用）

        Returns:
            エージェントのレスポンス
        """
        # default_paramsをベースに、Noneでないパラメータで上書き
        model_params = {**self.default_params}
        if temperature is not None:
            model_params["temperature"] = temperature
        if max_tokens is not None:
            model_params["max_tokens"] = max_tokens

        # strands Agentの__call__を使用し、生成パラメータを渡す
        return self(prompt, model_params=model_params)

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
        litellm_settings = settings.litellm

        return cls(
            model_id=litellm_settings.model_id,
            client_args=litellm_settings.client_args or None,
            default_params=litellm_settings.params or None,
        )
