"""スレッド履歴取得モジュール

スレッド内の過去のメッセージを取得します。
"""

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.exceptions import SlackAPIError
from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage
from nyao.integrations.slack.utils import UserNameCache, convert_to_slack_message

logger = get_logger(__name__)


class ThreadHistoryFetcher:
    """スレッド履歴の取得を担当

    スレッド内のメッセージを取得し、SlackMessageリストとして返します。
    Bot自身のメッセージも含みます（コンテキスト理解に必要）。
    """

    DEFAULT_LIMIT = 100

    def __init__(self, client: AsyncWebClient) -> None:
        """初期化

        Args:
            client: Slack AsyncWebClient インスタンス
        """
        self._client = client
        self._user_name_cache = UserNameCache(client)

    async def fetch_thread_messages(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = DEFAULT_LIMIT,
    ) -> list[SlackMessage]:
        """スレッド内のメッセージを取得

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドの親メッセージのタイムスタンプ
            limit: 取得する最大メッセージ数

        Returns:
            SlackMessageのリスト（時系列順）

        Raises:
            SlackAPIError: API呼び出しエラー時
        """
        logger.debug(
            "fetching_thread_messages",
            channel_id=channel_id,
            thread_ts=thread_ts,
            limit=limit,
        )

        try:
            response = await self._client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=limit,
            )
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown_error")
            logger.warning(
                "slack_api_error",
                error_code=error_code,
                channel_id=channel_id,
                thread_ts=thread_ts,
            )
            raise SlackAPIError(
                message=str(e),
                error_code=error_code,
            ) from e

        messages: list[SlackMessage] = []
        for msg in response.get("messages", []):
            # システムメッセージ（subtypeあり）はスキップ（ただしthread_broadcastは含める）
            subtype = msg.get("subtype")
            if subtype and subtype not in ("thread_broadcast", "file_share"):
                continue

            slack_message = await convert_to_slack_message(msg, channel_id, self._user_name_cache)
            messages.append(slack_message)

        logger.info(
            "thread_messages_fetched",
            channel_id=channel_id,
            thread_ts=thread_ts,
            message_count=len(messages),
        )

        return messages
