"""チャンネル履歴取得モジュール

チャンネル内の過去のメッセージ（スレッドに属さないもの）を取得します。
"""

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.exceptions import SlackAPIError
from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage
from nyao.integrations.slack.utils import UserNameCache, convert_to_slack_message

logger = get_logger(__name__)


class ChannelHistoryFetcher:
    """チャンネル履歴の取得を担当

    チャンネル内のメッセージを取得し、SlackMessageリストとして返します。
    スレッド返信は除外しますが、スレッド親メッセージは含みます。
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

    async def fetch_channel_messages(
        self,
        channel_id: str,
        limit: int = DEFAULT_LIMIT,
        oldest: float | None = None,
    ) -> list[SlackMessage]:
        """チャンネル内のメッセージを取得

        Args:
            channel_id: チャンネルID
            limit: 取得する最大メッセージ数
            oldest: 取得開始時刻（UNIXタイムスタンプ）

        Returns:
            SlackMessageのリスト（時系列順）
            - スレッドの親メッセージは含む
            - スレッド内の返信は含まない

        Raises:
            SlackAPIError: API呼び出しエラー時
        """
        logger.debug(
            "fetching_channel_messages",
            channel_id=channel_id,
            limit=limit,
            oldest=oldest,
        )

        try:
            response = await self._client.conversations_history(
                channel=channel_id,
                limit=limit,
                oldest=str(oldest) if oldest is not None else None,
            )
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown_error")
            logger.warning(
                "slack_api_error",
                error_code=error_code,
                channel_id=channel_id,
            )
            raise SlackAPIError(
                message=str(e),
                error_code=error_code,
            ) from e

        messages: list[SlackMessage] = []
        for msg in response.get("messages", []):
            # システムメッセージ（subtypeあり）はスキップ（ただし一部は含める）
            subtype = msg.get("subtype")
            if subtype and subtype not in ("thread_broadcast", "file_share"):
                continue

            # スレッド返信は除外（thread_tsがあり、かつtsと異なる場合）
            ts = msg.get("ts", "")
            thread_ts = msg.get("thread_ts")
            if thread_ts and thread_ts != ts:
                # これはスレッド返信なのでスキップ
                continue

            slack_message = await convert_to_slack_message(msg, channel_id, self._user_name_cache)
            messages.append(slack_message)

        # Slack APIは新しい順に返すので、古い順（時系列順）に並べ替える
        messages.reverse()

        logger.info(
            "channel_messages_fetched",
            channel_id=channel_id,
            message_count=len(messages),
        )

        return messages
