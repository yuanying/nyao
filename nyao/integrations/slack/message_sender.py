"""メッセージ送信モジュール

Slackへのメッセージ送信を担当します。
"""

from typing import Any, cast

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.exceptions import SlackAPIError
from nyao.core.logging import get_logger
from nyao.utils.retry import retry_async

logger = get_logger(__name__)


class MessageSender:
    """Slackへのメッセージ送信を担当

    リトライ機能付きでメッセージを送信します。
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF = 2.0

    def __init__(self, client: AsyncWebClient) -> None:
        """初期化

        Args:
            client: Slack AsyncWebClient インスタンス
        """
        self._client = client

    async def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
    ) -> str:
        """メッセージを送信

        Args:
            channel_id: 送信先チャンネルID
            text: メッセージ本文
            thread_ts: スレッドの親メッセージのタイムスタンプ（スレッド返信時）

        Returns:
            送信されたメッセージのタイムスタンプ

        Raises:
            SlackAPIError: API呼び出しエラー時
        """
        logger.debug(
            "sending_message",
            channel_id=channel_id,
            thread_ts=thread_ts,
            text_length=len(text),
        )

        try:
            response = cast(
                dict[str, Any],
                await retry_async(
                    self._post_message,
                    channel_id=channel_id,
                    text=text,
                    thread_ts=thread_ts,
                    max_retries=self.MAX_RETRIES,
                    delay=self.RETRY_DELAY,
                    backoff=self.RETRY_BACKOFF,
                    exceptions=(SlackAPIError,),
                    skip_on=lambda e: isinstance(e, SlackAPIError) and not e.is_retryable(),
                ),
            )
            ts: str = response["ts"]
            logger.info(
                "message_sent",
                channel_id=channel_id,
                thread_ts=thread_ts,
                message_ts=ts,
            )
            return ts
        except SlackAPIError:
            raise

    async def _post_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None,
    ) -> dict[str, Any]:
        """内部メッセージ送信（エラー変換付き）

        Args:
            channel_id: 送信先チャンネルID
            text: メッセージ本文
            thread_ts: スレッドの親メッセージのタイムスタンプ

        Returns:
            Slack APIレスポンス

        Raises:
            SlackAPIError: API呼び出しエラー時
        """
        try:
            response = await self._client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts,
            )
            # デュアルパス処理:
            # - 実際のSlack API: AsyncSlackResponseオブジェクトを返す（.data属性あり）
            # - テストのモック: 直接dictを返す
            # 両方のケースに対応するため、.data属性の有無で分岐
            if hasattr(response, "data"):
                return cast(dict[str, Any], response.data)
            return cast(dict[str, Any], response)
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
