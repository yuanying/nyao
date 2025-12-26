"""イベント受信モジュール

Slackからのイベントを受信し、内部データモデルに変換します。
"""

from collections.abc import Callable
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage
from nyao.integrations.slack.utils import UserNameCache, convert_to_slack_message

logger = get_logger(__name__)

# 処理するサブタイプ（None = 通常メッセージ）
ALLOWED_SUBTYPES = {
    None,
    "file_share",
    "thread_broadcast",
}


class EventReceiver:
    """Slackイベントの受信と変換を担当

    メッセージイベントとリアクションイベントを処理し、
    内部データモデルに変換します。
    """

    def __init__(
        self,
        client: AsyncWebClient,
        bot_user_id: str,
    ) -> None:
        """初期化

        Args:
            client: Slack AsyncWebClient インスタンス
            bot_user_id: Bot自身のユーザーID（無視用）
        """
        self._client = client
        self._bot_user_id = bot_user_id
        self._user_name_cache = UserNameCache(client)

    async def handle_message_event(
        self,
        event: dict[str, Any],
        say: Callable,
    ) -> SlackMessage | None:
        """メッセージイベントを処理

        Args:
            event: Slackからのメッセージイベントペイロード
            say: Bolt提供のメッセージ送信関数

        Returns:
            SlackMessage（処理対象の場合）、None（無視する場合）
        """
        # Botからのメッセージは無視
        if "bot_id" in event:
            logger.debug(
                "ignoring_bot_message",
                bot_id=event.get("bot_id"),
            )
            return None

        # システムメッセージは無視
        subtype = event.get("subtype")
        if subtype not in ALLOWED_SUBTYPES:
            logger.debug(
                "ignoring_message_subtype",
                subtype=subtype,
            )
            return None

        # ユーザーIDがない場合は無視
        user_id = event.get("user")
        if not user_id:
            logger.debug("ignoring_message_without_user")
            return None

        channel_id = event.get("channel", "")
        ts = event.get("ts", "")

        logger.debug(
            "processing_message_event",
            channel_id=channel_id,
            user_id=user_id,
            ts=ts,
        )

        slack_message = await convert_to_slack_message(event, channel_id, self._user_name_cache)

        logger.info(
            "message_event_processed",
            channel_id=channel_id,
            user_id=user_id,
            ts=ts,
            thread_ts=slack_message.thread_ts,
        )

        return slack_message

    async def handle_reaction_event(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        """リアクションイベントを処理

        Args:
            event: Slackからのreaction_addedイベントペイロード

        Returns:
            処理済みリアクション情報（処理対象の場合）、None（無視する場合）
        """
        user_id = event.get("user", "")

        # Bot自身のリアクションは無視
        if user_id == self._bot_user_id:
            logger.debug(
                "ignoring_bot_reaction",
                user_id=user_id,
            )
            return None

        item = event.get("item", {})
        channel_id = item.get("channel", "")
        message_ts = item.get("ts", "")
        reaction = event.get("reaction", "")

        logger.info(
            "reaction_event_processed",
            channel_id=channel_id,
            user_id=user_id,
            message_ts=message_ts,
            reaction=reaction,
        )

        return {
            "user": user_id,
            "reaction": reaction,
            "channel": channel_id,
            "message_ts": message_ts,
        }
