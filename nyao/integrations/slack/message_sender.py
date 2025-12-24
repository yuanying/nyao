"""メッセージ送信

Slackチャンネルにメッセージを送信します。
"""

import asyncio

from typing import Any, cast

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.exceptions import SlackAPIError
from nyao.core.logging import get_logger

logger = get_logger(__name__)


class MessageSender:
    """Slackメッセージ送信を担当するクラス"""

    def __init__(
        self,
        client: AsyncWebClient,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """MessageSenderを初期化

        Args:
            client: Slack AsyncWebClient
            max_retries: 最大リトライ回数
            retry_delay: リトライ間隔（秒）
        """
        self._client = client
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._logger = get_logger(__name__)

    async def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """メッセージを送信（リトライ機能付き）

        Args:
            channel_id: 送信先チャンネルID
            text: メッセージ本文
            thread_ts: スレッドのタイムスタンプ（スレッド返信の場合）

        Returns:
            Slack APIのレスポンス

        Raises:
            SlackAPIError: 送信に失敗した場合
        """
        last_exception: SlackAPIError | None = None
        delay = self._retry_delay

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.chat_postMessage(
                    channel=channel_id,
                    text=text,
                    thread_ts=thread_ts,
                )

                self._logger.info(
                    "message_sent",
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    message_ts=response.get("ts"),
                )

                return cast(dict[str, Any], response)

            except SlackApiError as e:
                error_code = self._get_error_code(e)
                slack_error = SlackAPIError(
                    message=str(e),
                    error_code=error_code,
                )

                # リトライ不可能なエラーは即座に失敗
                if not slack_error.is_retryable():
                    self._logger.error(
                        "message_send_failed",
                        channel_id=channel_id,
                        error_code=error_code,
                        retryable=False,
                    )
                    raise slack_error from e

                last_exception = slack_error

                # リトライ上限に達した場合
                if attempt >= self._max_retries:
                    self._logger.error(
                        "message_send_retry_exhausted",
                        channel_id=channel_id,
                        error_code=error_code,
                        max_retries=self._max_retries,
                    )
                    raise slack_error from e

                # レート制限の場合はRetry-Afterヘッダーを参照
                wait_time = delay
                if error_code == "ratelimited":
                    retry_after = self._get_retry_after(e)
                    if retry_after:
                        wait_time = retry_after

                self._logger.warning(
                    "message_send_retry",
                    channel_id=channel_id,
                    error_code=error_code,
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    wait_time=wait_time,
                )

                await asyncio.sleep(wait_time)
                delay *= 2  # 指数バックオフ

        # ここには到達しないはずだが、型チェッカーのために必要
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry loop exit")

    def _get_error_code(self, error: SlackApiError) -> str:
        """SlackApiErrorからエラーコードを取得

        Args:
            error: SlackApiError

        Returns:
            エラーコード
        """
        if hasattr(error.response, "get"):
            return error.response.get("error", str(error))
        return str(error)

    def _get_retry_after(self, error: SlackApiError) -> float | None:
        """SlackApiErrorからRetry-After値を取得

        Args:
            error: SlackApiError

        Returns:
            待機時間（秒）、取得できない場合はNone
        """
        if hasattr(error.response, "headers"):
            retry_after = error.response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return None
