"""応答生成エージェント

Slackメッセージに対して友達のように自然な返信を生成するエージェントを提供します。
"""

from nyao.config.settings import LiteLLMSettings
from nyao.core.logging import get_logger
from nyao.core.models import ConversationContext, LLMResponse, SlackMessage
from nyao.integrations.llm.agent_base import NyaoAgent
from nyao.integrations.llm.prompts import PromptManager

logger = get_logger(__name__)


class ResponseGeneratorAgent:
    """応答生成エージェント

    Slackメッセージに対して友達のように自然な返信を生成します。
    LLMを使用して応答を生成し、エラー時はLLMAPIErrorをスローして上位レイヤーで処理します。
    """

    # LLM呼び出しパラメータ
    TEMPERATURE = 0.8  # 多様性を重視
    MAX_TOKENS = 300

    def __init__(
        self,
        settings: LiteLLMSettings,
        persona: str | None = None,
    ) -> None:
        """ResponseGeneratorAgentを初期化

        Args:
            settings: LiteLLM設定
            persona: ボットのペルソナ設定（オプション）
        """
        self._settings = settings
        self._prompt_manager = PromptManager(persona=persona)
        self._agent = NyaoAgent(settings=settings)

        logger.info(
            "response_generator_agent_initialized",
            model_id=settings.model_id,
            has_custom_persona=persona is not None,
        )

    async def generate_response(
        self,
        message: SlackMessage,
        thread_context: ConversationContext | None = None,
        channel_context: ConversationContext | None = None,
    ) -> LLMResponse:
        """メッセージに対する応答を生成

        Args:
            message: 返信対象のSlackメッセージ
            thread_context: スレッドコンテキスト（オプション）
            channel_context: チャンネルコンテキスト（オプション）

        Returns:
            LLMResponse: 生成された応答

        Raises:
            LLMAPIError: API呼び出しエラー時
        """
        logger.debug(
            "generate_response_start",
            message_id=message.message_id,
            has_thread_context=thread_context is not None,
            has_channel_context=channel_context is not None,
        )

        # プロンプトを構築
        prompt = self._prompt_manager.build_response_generation_prompt(
            message=message,
            thread_context=thread_context,
            channel_context=channel_context,
        )

        # LLMを呼び出し（エラーはそのままスロー）
        response = await self._agent.call_llm(
            prompt=prompt,
            temperature=self.TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
        )

        logger.info(
            "generate_response_success",
            message_id=message.message_id,
            content_length=len(response.content),
        )

        return response
