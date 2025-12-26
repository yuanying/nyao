"""応答生成サービス

LLMを使用して、適切な応答メッセージを生成します。
"""

import random

from nyao.core.exceptions import LLMAPIError
from nyao.core.logging import get_logger
from nyao.core.models import ConversationContext, SlackMessage
from nyao.integrations.llm.generator_agent import ResponseGeneratorAgent

logger = get_logger(__name__)


class ResponseGeneratorService:
    """応答生成サービス

    LLMを使用して、適切な応答メッセージを生成します。
    スレッドコンテキストとチャンネルコンテキストの両方を参照し、
    自然な応答を生成します。
    """

    FALLBACK_RESPONSES = [
        "そうなんだね！",
        "なるほど",
        "へぇ〜",
        "わかる〜",
        "それはいいね！",
        "なるほどね〜",
        "うんうん",
        "そっか！",
        "いいね！",
    ]

    def __init__(
        self,
        generator_agent: ResponseGeneratorAgent,
    ) -> None:
        """初期化

        Args:
            generator_agent: LLMによる応答生成を行うエージェント
        """
        self._generator_agent = generator_agent

        logger.info("response_generator_service_initialized")

    async def generate_response(
        self,
        message: SlackMessage,
        thread_context: ConversationContext | None = None,
        channel_context: ConversationContext | None = None,
    ) -> str:
        """応答メッセージを生成

        Args:
            message: 返信対象のSlackメッセージ
            thread_context: スレッドコンテキスト（オプション）
            channel_context: チャンネルコンテキスト（オプション）

        Returns:
            生成された応答メッセージ（エラー時はフォールバック応答）
        """
        logger.debug(
            "generate_response_start",
            message_id=message.message_id,
            has_thread_context=thread_context is not None,
            has_channel_context=channel_context is not None,
        )

        try:
            # LLMで応答を生成
            llm_response = await self._generator_agent.generate_response(
                message=message,
                thread_context=thread_context,
                channel_context=channel_context,
            )

            # 後処理を適用
            processed_response = self._post_process_response(llm_response.content)

            logger.info(
                "generate_response_success",
                message_id=message.message_id,
                response_length=len(processed_response),
            )

            return processed_response

        except LLMAPIError as e:
            logger.warning(
                "generate_response_llm_error",
                message_id=message.message_id,
                error=str(e),
            )
            return self._get_fallback_response()

        except Exception as e:
            logger.error(
                "generate_response_unexpected_error",
                message_id=message.message_id,
                error=str(e),
            )
            return self._get_fallback_response()

    def _post_process_response(self, response: str) -> str:
        """応答の後処理

        処理内容:
        1. 前後の空白を削除（strip）
        2. 引用符を削除（ダブルクォート、シングルクォート、日本語カギ括弧）

        Args:
            response: LLMからの生の応答

        Returns:
            後処理済みの応答
        """
        # 1. 前後の空白を削除
        processed = response.strip()

        # 2. 引用符を削除
        # ダブルクォートで囲まれている場合
        if processed.startswith('"') and processed.endswith('"'):
            processed = processed[1:-1].strip()
        # シングルクォートで囲まれている場合
        elif processed.startswith("'") and processed.endswith("'"):
            processed = processed[1:-1].strip()
        # 日本語カギ括弧で囲まれている場合
        elif processed.startswith("「") and processed.endswith("」"):
            processed = processed[1:-1].strip()

        return processed

    def _get_fallback_response(self) -> str:
        """フォールバック応答を取得

        Returns:
            ランダムに選択されたフォールバック応答
        """
        return random.choice(self.FALLBACK_RESPONSES)
