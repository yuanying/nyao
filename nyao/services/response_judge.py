"""応答判定サービス

メッセージに対して応答すべきかどうかを総合的に判定します。
"""

from datetime import UTC, datetime

from nyao.core.logging import get_logger
from nyao.core.models import ResponseDecision, SlackMessage
from nyao.integrations.llm.judge_agent import ResponseJudgeAgent

logger = get_logger(__name__)


class ResponseJudgeService:
    """応答判定サービス

    メッセージに対して応答すべきかどうかを総合的に判定します。
    基本条件チェックを行った後、LLMによる高度な判定を実行します。
    """

    MIN_MESSAGE_LENGTH = 3

    def __init__(
        self,
        judge_agent: ResponseJudgeAgent,
        response_delay: int = 60,
    ) -> None:
        """初期化

        Args:
            judge_agent: LLMによる判定を行うエージェント
            response_delay: 応答遅延時間（秒）
        """
        self._judge_agent = judge_agent
        self._response_delay = response_delay

        logger.info(
            "response_judge_service_initialized",
            response_delay=response_delay,
        )

    @property
    def response_delay(self) -> int:
        """応答遅延時間を取得"""
        return self._response_delay

    async def should_respond_to_message(
        self,
        message: SlackMessage,
        reactions: list[str],
        reply_count: int,
    ) -> ResponseDecision:
        """メッセージに応答すべきか判定

        Args:
            message: 判定対象のSlackメッセージ
            reactions: 現在のリアクションリスト
            reply_count: 現在の返信数

        Returns:
            ResponseDecision: 判定結果
        """
        logger.debug(
            "should_respond_check_start",
            message_id=message.message_id,
            reaction_count=len(reactions),
            reply_count=reply_count,
        )

        # 1. 基本条件チェック
        basic_result = self._check_basic_conditions(message)
        if basic_result is not None:
            logger.info(
                "should_respond_basic_condition_failed",
                message_id=message.message_id,
                reason=basic_result.reason,
            )
            return basic_result

        # 2. 経過時間計算
        elapsed_seconds = self._calculate_elapsed_time(message)

        # 3. LLMによる判定
        result = await self._judge_agent.judge_should_respond(
            message=message,
            elapsed_seconds=elapsed_seconds,
            reaction_count=len(reactions),
            reply_count=reply_count,
        )

        logger.info(
            "should_respond_llm_decision",
            message_id=message.message_id,
            should_respond=result.should_respond,
            confidence=result.confidence,
        )

        return result

    def _check_basic_conditions(self, message: SlackMessage) -> ResponseDecision | None:
        """基本条件チェック

        Args:
            message: 判定対象のメッセージ

        Returns:
            条件を満たさない場合はResponseDecision
            条件を満たす場合はNone
        """
        text = message.text.strip()

        # 空メッセージチェック
        if not text:
            return ResponseDecision(
                should_respond=False,
                reason="メッセージが空です",
                confidence=1.0,
            )

        # 長さチェック
        if len(text) < self.MIN_MESSAGE_LENGTH:
            return ResponseDecision(
                should_respond=False,
                reason=f"メッセージが短すぎます（{self.MIN_MESSAGE_LENGTH}文字未満）",
                confidence=1.0,
            )

        return None

    def _calculate_elapsed_time(self, message: SlackMessage) -> int:
        """経過時間を計算

        Args:
            message: 判定対象のメッセージ

        Returns:
            メッセージ投稿からの経過秒数
        """
        now = datetime.now(UTC)
        elapsed = now - message.timestamp
        return int(elapsed.total_seconds())
