"""スレッド履歴取得

スレッド内の過去のメッセージを取得します。
"""

from datetime import UTC, datetime

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.exceptions import SlackAPIError
from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage
from nyao.integrations.slack.event_receiver import EventReceiver

logger = get_logger(__name__)


class ThreadHistoryFetcher:
    """スレッド履歴を取得するクラス"""

    def __init__(
        self,
        client: AsyncWebClient,
        event_receiver: EventReceiver,
    ) -> None:
        """ThreadHistoryFetcherを初期化

        Args:
            client: Slack AsyncWebClient
            event_receiver: EventReceiverインスタンス（ユーザー情報キャッシュを共有）
        """
        self._client = client
        self._event_receiver = event_receiver
        self._logger = get_logger(__name__)

    async def fetch_thread_messages(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 100,
        include_bot_messages: bool = False,
    ) -> list[SlackMessage]:
        """スレッド内のメッセージを取得

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドのタイムスタンプ
            limit: 取得するメッセージの最大数
            include_bot_messages: Bot自身のメッセージを含めるか

        Returns:
            SlackMessageのリスト（時系列順）

        Raises:
            SlackAPIError: 取得に失敗した場合
        """
        try:
            response = await self._client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=limit,
            )

            self._logger.info(
                "thread_history_fetched",
                channel_id=channel_id,
                thread_ts=thread_ts,
                message_count=len(response.get("messages", [])),
            )

            messages: list[SlackMessage] = []
            for msg in response.get("messages", []):
                # Botメッセージのフィルタリング
                if not include_bot_messages:
                    if self._is_bot_message(msg):
                        continue

                slack_message = await self._convert_message(msg, channel_id)
                messages.append(slack_message)

            # 時系列順にソート（古い順）
            messages.sort(key=lambda m: m.timestamp)

            return messages

        except SlackApiError as e:
            error_code = e.response.get("error") if hasattr(e.response, "get") else str(e)
            self._logger.error(
                "thread_history_fetch_failed",
                channel_id=channel_id,
                thread_ts=thread_ts,
                error_code=error_code,
            )
            raise SlackAPIError(
                message=str(e),
                error_code=error_code,
            ) from e

    def _is_bot_message(self, message: dict) -> bool:
        """Botメッセージかどうかを判定

        Args:
            message: メッセージデータ

        Returns:
            Botメッセージの場合True
        """
        # bot_idがある場合
        if message.get("bot_id"):
            return True

        # EventReceiverのbot_user_idと一致する場合
        if message.get("user") == self._event_receiver._bot_user_id:
            return True

        return False

    async def _convert_message(self, message: dict, channel_id: str) -> SlackMessage:
        """APIレスポンスのメッセージをSlackMessageに変換

        Args:
            message: APIレスポンスのメッセージ
            channel_id: チャンネルID

        Returns:
            SlackMessageオブジェクト
        """
        user_id = message.get("user", "")
        user_name = await self._event_receiver.get_user_name(user_id)

        ts = message.get("ts", "0")
        timestamp = datetime.fromtimestamp(float(ts), tz=UTC)

        # リアクションを取得
        reactions = []
        for reaction in message.get("reactions", []):
            reactions.append(reaction["name"])

        return SlackMessage(
            message_id=ts,
            channel_id=channel_id,
            thread_ts=message.get("thread_ts"),
            user_id=user_id,
            user_name=user_name,
            text=message.get("text", ""),
            timestamp=timestamp,
            reactions=reactions,
            reply_count=message.get("reply_count", 0),
        )
