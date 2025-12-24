"""イベント受信

Slackからのイベントを受信し、内部データモデルに変換します。
"""

import time
from datetime import UTC, datetime

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.exceptions import SlackAPIError
from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage

logger = get_logger(__name__)

# システムメッセージのサブタイプ
SYSTEM_MESSAGE_SUBTYPES = {
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
    "bot_add",
    "bot_remove",
    "reminder_add",
    "file_share",
    "message_changed",
    "message_deleted",
}


class UserInfoCache:
    """ユーザー情報のキャッシュ

    Slack APIへの呼び出し回数を削減するため、ユーザー情報をキャッシュします。
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """UserInfoCacheを初期化

        Args:
            ttl_seconds: キャッシュの有効期間（秒）
        """
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[str, float]] = {}

    def get(self, user_id: str) -> str | None:
        """キャッシュからユーザー名を取得

        Args:
            user_id: SlackユーザーID

        Returns:
            ユーザー名、キャッシュミスまたは期限切れの場合はNone
        """
        if user_id not in self._cache:
            return None

        user_name, cached_at = self._cache[user_id]
        if time.time() - cached_at > self._ttl_seconds:
            # 期限切れ
            del self._cache[user_id]
            return None

        return user_name

    def set(self, user_id: str, user_name: str) -> None:
        """ユーザー名をキャッシュに保存

        Args:
            user_id: SlackユーザーID
            user_name: ユーザー名
        """
        self._cache[user_id] = (user_name, time.time())

    def clear(self) -> None:
        """キャッシュをクリア"""
        self._cache.clear()


class EventReceiver:
    """Slackイベントを受信し内部モデルに変換するクラス"""

    def __init__(
        self,
        client: AsyncWebClient,
        monitored_channels: list[str],
        bot_user_id: str,
        user_cache_ttl: int = 3600,
    ) -> None:
        """EventReceiverを初期化

        Args:
            client: Slack AsyncWebClient
            monitored_channels: 監視対象チャンネルIDのリスト
            bot_user_id: Bot自身のユーザーID
            user_cache_ttl: ユーザー情報キャッシュの有効期間（秒）
        """
        self._client = client
        self._monitored_channels = set(monitored_channels)
        self._bot_user_id = bot_user_id
        self._user_cache = UserInfoCache(ttl_seconds=user_cache_ttl)
        self._logger = get_logger(__name__)

    @property
    def user_cache(self) -> UserInfoCache:
        """ユーザー情報キャッシュを取得"""
        return self._user_cache

    def is_monitored_channel(self, channel_id: str) -> bool:
        """チャンネルが監視対象かどうかを判定

        Args:
            channel_id: チャンネルID

        Returns:
            監視対象の場合True
        """
        return channel_id in self._monitored_channels

    def is_bot_message(self, event: dict) -> bool:
        """Bot自身のメッセージかどうかを判定

        Args:
            event: Slackイベント

        Returns:
            Bot自身のメッセージの場合True
        """
        # bot_idがある場合はBotメッセージ
        if event.get("bot_id"):
            return True

        # ユーザーIDがBot自身の場合
        if event.get("user") == self._bot_user_id:
            return True

        return False

    def is_system_message(self, event: dict) -> bool:
        """システムメッセージかどうかを判定

        Args:
            event: Slackイベント

        Returns:
            システムメッセージの場合True
        """
        subtype = event.get("subtype")
        return subtype in SYSTEM_MESSAGE_SUBTYPES

    async def get_user_name(self, user_id: str) -> str:
        """ユーザーIDからユーザー名を取得（キャッシュ機能付き）

        Args:
            user_id: SlackユーザーID

        Returns:
            ユーザーの表示名

        Raises:
            SlackAPIError: ユーザー情報取得に失敗した場合
        """
        # キャッシュを確認
        cached_name = self._user_cache.get(user_id)
        if cached_name is not None:
            return cached_name

        # APIから取得
        try:
            response = await self._client.users_info(user=user_id)
            profile = response["user"]["profile"]

            # display_name > real_name > user_id の優先順位
            user_name = profile.get("display_name") or profile.get("real_name") or user_id

            self._user_cache.set(user_id, user_name)
            return user_name

        except SlackApiError as e:
            error_code = e.response.get("error") if hasattr(e.response, "get") else str(e)
            self._logger.error(
                "user_info_fetch_failed",
                user_id=user_id,
                error_code=error_code,
            )
            raise SlackAPIError(
                message=str(e),
                error_code=error_code,
            ) from e

    async def convert_to_slack_message(self, event: dict) -> SlackMessage | None:
        """メッセージイベントをSlackMessageに変換

        Args:
            event: Slackメッセージイベント

        Returns:
            SlackMessageオブジェクト、変換対象外の場合はNone
        """
        channel_id = event.get("channel", "")

        # フィルタリング
        if not self.is_monitored_channel(channel_id):
            return None

        if self.is_bot_message(event):
            return None

        if self.is_system_message(event):
            return None

        # ユーザー名を取得
        user_id = event.get("user", "")
        user_name = await self.get_user_name(user_id)

        # タイムスタンプを変換
        ts = event.get("ts", "0")
        timestamp = datetime.fromtimestamp(float(ts), tz=UTC)

        # リアクションを取得
        reactions = []
        for reaction in event.get("reactions", []):
            reactions.append(reaction["name"])

        # SlackMessageを作成
        return SlackMessage(
            message_id=ts,
            channel_id=channel_id,
            thread_ts=event.get("thread_ts"),
            user_id=user_id,
            user_name=user_name,
            text=event.get("text", ""),
            timestamp=timestamp,
            reactions=reactions,
            reply_count=event.get("reply_count", 0),
        )

    async def handle_message_event(
        self,
        event: dict,
        say,
    ) -> SlackMessage | None:
        """メッセージイベントを処理

        Args:
            event: Slackメッセージイベント
            say: メッセージ送信用関数

        Returns:
            変換されたSlackMessage、処理対象外の場合はNone
        """
        message = await self.convert_to_slack_message(event)

        if message is not None:
            self._logger.info(
                "message_received",
                channel_id=message.channel_id,
                user_id=message.user_id,
                thread_ts=message.thread_ts,
            )

        return message

    async def handle_reaction_event(self, event: dict) -> dict | None:
        """リアクションイベントを処理

        Args:
            event: Slackリアクションイベント

        Returns:
            処理されたリアクション情報、対象外の場合はNone
        """
        item = event.get("item", {})
        channel_id = item.get("channel", "")

        if not self.is_monitored_channel(channel_id):
            return None

        result = {
            "reaction": event.get("reaction"),
            "user_id": event.get("user"),
            "channel_id": channel_id,
            "message_ts": item.get("ts"),
        }

        self._logger.info(
            "reaction_received",
            channel_id=channel_id,
            reaction=result["reaction"],
        )

        return result
