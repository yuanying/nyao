"""MessageSenderのテスト"""

from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from nyao.core.exceptions import SlackAPIError
from nyao.integrations.slack.message_sender import MessageSender


class TestMessageSender:
    """MessageSenderのテスト"""

    async def test_send_message_success(self, mock_web_client: AsyncMock) -> None:
        """メッセージ送信成功"""
        mock_web_client.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.123456",
        }

        sender = MessageSender(mock_web_client)
        result = await sender.send_message(
            channel_id="C12345",
            text="Hello, world!",
        )

        assert result == "1234567890.123456"
        mock_web_client.chat_postMessage.assert_called_once_with(
            channel="C12345",
            text="Hello, world!",
            thread_ts=None,
        )

    async def test_send_message_to_thread(self, mock_web_client: AsyncMock) -> None:
        """スレッド返信成功"""
        mock_web_client.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.654321",
        }

        sender = MessageSender(mock_web_client)
        result = await sender.send_message(
            channel_id="C12345",
            text="Thread reply!",
            thread_ts="1234567890.123456",
        )

        assert result == "1234567890.654321"
        mock_web_client.chat_postMessage.assert_called_once_with(
            channel="C12345",
            text="Thread reply!",
            thread_ts="1234567890.123456",
        )

    async def test_send_message_retry_on_rate_limit(self, mock_web_client: AsyncMock) -> None:
        """レート制限時のリトライ"""
        # 1回目: rate_limited、2回目: 成功
        rate_limit_error = SlackApiError(
            message="rate_limited",
            response={"error": "rate_limited", "headers": {"Retry-After": "1"}},
        )
        mock_web_client.chat_postMessage.side_effect = [
            rate_limit_error,
            {"ok": True, "ts": "1234567890.123456"},
        ]

        sender = MessageSender(mock_web_client)
        result = await sender.send_message(
            channel_id="C12345",
            text="Hello, world!",
        )

        assert result == "1234567890.123456"
        assert mock_web_client.chat_postMessage.call_count == 2

    async def test_send_message_retry_on_server_error(self, mock_web_client: AsyncMock) -> None:
        """サーバーエラー時のリトライ"""
        # 1回目: internal_error、2回目: 成功
        server_error = SlackApiError(
            message="internal_error",
            response={"error": "internal_error"},
        )
        mock_web_client.chat_postMessage.side_effect = [
            server_error,
            {"ok": True, "ts": "1234567890.123456"},
        ]

        sender = MessageSender(mock_web_client)
        result = await sender.send_message(
            channel_id="C12345",
            text="Hello, world!",
        )

        assert result == "1234567890.123456"
        assert mock_web_client.chat_postMessage.call_count == 2

    async def test_send_message_max_retries_exceeded(self, mock_web_client: AsyncMock) -> None:
        """リトライ上限超過でSlackAPIError"""
        rate_limit_error = SlackApiError(
            message="rate_limited",
            response={"error": "rate_limited"},
        )
        mock_web_client.chat_postMessage.side_effect = rate_limit_error

        sender = MessageSender(mock_web_client)

        with pytest.raises(SlackAPIError) as exc_info:
            await sender.send_message(
                channel_id="C12345",
                text="Hello, world!",
            )

        assert exc_info.value.error_code == "rate_limited"
        # 最初の1回 + リトライ3回 = 4回
        assert mock_web_client.chat_postMessage.call_count == 4

    async def test_send_message_no_retry_on_client_error(self, mock_web_client: AsyncMock) -> None:
        """400系エラーはリトライしない"""
        channel_not_found_error = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )
        mock_web_client.chat_postMessage.side_effect = channel_not_found_error

        sender = MessageSender(mock_web_client)

        with pytest.raises(SlackAPIError) as exc_info:
            await sender.send_message(
                channel_id="INVALID",
                text="Hello, world!",
            )

        assert exc_info.value.error_code == "channel_not_found"
        # リトライなしで即座にエラー
        assert mock_web_client.chat_postMessage.call_count == 1
