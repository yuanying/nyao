"""Slack連携ユーティリティ

Slack連携モジュールで共通して使用するユーティリティ関数・クラスを提供します。
"""

from datetime import UTC, datetime
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage

logger = get_logger(__name__)


class UserNameCache:
    """ユーザー名のキャッシュ

    Slack APIへの呼び出し回数を削減するため、ユーザー名をキャッシュします。
    """

    def __init__(self, client: AsyncWebClient) -> None:
        """初期化

        Args:
            client: Slack AsyncWebClient インスタンス
        """
        self._client = client
        self._cache: dict[str, str] = {}

    async def get_user_name(self, user_id: str) -> str:
        """ユーザー名を取得（キャッシュ優先）

        Args:
            user_id: ユーザーID

        Returns:
            ユーザー名
        """
        if user_id in self._cache:
            return self._cache[user_id]

        try:
            response = await self._client.users_info(user=user_id)
            user = response.get("user", {})
            user_name = user.get("real_name") or user.get("name") or user_id
            self._cache[user_id] = user_name
            return user_name
        except SlackApiError:
            logger.warning("failed_to_get_user_name", user_id=user_id)
            return user_id


async def convert_to_slack_message(
    msg: dict[str, Any],
    channel_id: str,
    user_name_cache: UserNameCache,
) -> SlackMessage:
    """Slack APIレスポンスをSlackMessageに変換

    Args:
        msg: Slack APIからのメッセージ
        channel_id: チャンネルID
        user_name_cache: ユーザー名キャッシュ

    Returns:
        SlackMessageインスタンス
    """
    user_id = msg.get("user", "unknown")
    user_name = await user_name_cache.get_user_name(user_id)

    # リアクションを抽出
    reactions = [r["name"] for r in msg.get("reactions", [])]

    # タイムスタンプをdatetimeに変換
    ts = msg.get("ts", "0")
    timestamp = datetime.fromtimestamp(float(ts), tz=UTC)

    return SlackMessage(
        message_id=ts,
        channel_id=channel_id,
        thread_ts=msg.get("thread_ts"),
        user_id=user_id,
        user_name=user_name,
        text=msg.get("text", ""),
        timestamp=timestamp,
        reactions=reactions,
        reply_count=msg.get("reply_count", 0),
    )
