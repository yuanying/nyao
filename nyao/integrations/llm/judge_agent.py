"""応答判定エージェント

Slackメッセージに対して応答すべきかどうかを判定するエージェントを提供します。
"""

from nyao.config.settings import LiteLLMSettings
from nyao.core.exceptions import LLMAPIError
from nyao.core.logging import get_logger
from nyao.core.models import ResponseDecision, SlackMessage
from nyao.integrations.llm.agent_base import NyaoAgent
from nyao.integrations.llm.prompts import PromptManager

logger = get_logger(__name__)


class ResponseJudgeAgent:
    """応答判定エージェント

    Slackメッセージに対して応答すべきかどうかを判定します。
    LLMを使用して判定を行い、エラー時は安全側（応答しない）に倒します。
    strands-agentsのStructured Output機能を使用して、型安全な判定結果を取得します。
    """

    # LLM呼び出しパラメータ
    TEMPERATURE = 0.3  # 一貫性を重視
    MAX_TOKENS = 200

    def __init__(
        self,
        settings: LiteLLMSettings,
        persona: str | None = None,
    ) -> None:
        """ResponseJudgeAgentを初期化

        Args:
            settings: LiteLLM設定
            persona: ボットのペルソナ設定（オプション）
        """
        self._settings = settings
        self._prompt_manager = PromptManager(persona=persona)
        self._agent = NyaoAgent(settings=settings)

        logger.info(
            "response_judge_agent_initialized",
            model_id=settings.model_id,
            has_custom_persona=persona is not None,
        )

    async def judge_should_respond(
        self,
        message: SlackMessage,
        elapsed_seconds: int,
        reaction_count: int,
        reply_count: int,
    ) -> ResponseDecision:
        """メッセージに対して応答すべきかどうかを判定

        strands-agentsのStructured Output機能を使用して、
        ResponseDecisionモデルに基づいた型安全な判定結果を取得します。

        Args:
            message: 判定対象のSlackメッセージ
            elapsed_seconds: メッセージ投稿からの経過秒数
            reaction_count: リアクション数
            reply_count: 返信数

        Returns:
            ResponseDecision: 判定結果
        """
        logger.debug(
            "judge_should_respond_start",
            message_id=message.message_id,
            elapsed_seconds=elapsed_seconds,
            reaction_count=reaction_count,
            reply_count=reply_count,
        )

        try:
            # プロンプトを構築
            prompt = self._prompt_manager.build_should_respond_prompt(
                message=message,
                elapsed_seconds=elapsed_seconds,
                reaction_count=reaction_count,
                reply_count=reply_count,
            )

            # Structured Outputを使用してLLMを呼び出し
            decision = await self._agent.structured_output(
                output_model=ResponseDecision,
                prompt=prompt,
                temperature=self.TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )

            logger.info(
                "judge_should_respond_success",
                message_id=message.message_id,
                should_respond=decision.should_respond,
                confidence=decision.confidence,
            )

            return decision

        except LLMAPIError as e:
            logger.warning(
                "judge_should_respond_llm_error",
                message_id=message.message_id,
                error=str(e),
            )
            return self._create_fallback_decision("LLMエラーにより判定不可")

        except Exception as e:
            logger.error(
                "judge_should_respond_unexpected_error",
                message_id=message.message_id,
                error=str(e),
            )
            return self._create_fallback_decision(f"予期しないエラー: {e}")

    def _create_fallback_decision(self, reason: str) -> ResponseDecision:
        """フォールバック用のResponseDecisionを作成

        Args:
            reason: フォールバック理由

        Returns:
            ResponseDecision: 応答しない判定
        """
        return ResponseDecision(
            should_respond=False,
            reason=reason,
            confidence=0.0,
        )
