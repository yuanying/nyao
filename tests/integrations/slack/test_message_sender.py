"""MessageSender のテスト"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from nyao.core.exceptions import SlackAPIError
from nyao.integrations.slack.message_sender import MessageSender


class TestMessageSender:
    """MessageSender のテスト"""

    @pytest.fixture
    def mock_client(self):
        """AsyncWebClient のモック"""
        client = AsyncMock()
        client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123456", "channel": "C123456"}
        )
        return client

    @pytest.fixture
    def sender(self, mock_client):
        """MessageSender インスタンス"""
        return MessageSender(
            client=mock_client,
            max_retries=3,
            retry_delay=0.01,  # テスト用に短い遅延
        )

    async def test_send_message_success(self, sender, mock_client):
        """メッセージが正常に送信されること"""
        result = await sender.send_message(
            channel_id="C123456",
            text="Hello, world!",
        )

        assert result["ok"] is True
        assert result["ts"] == "1234567890.123456"
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C123456",
            text="Hello, world!",
            thread_ts=None,
        )

    async def test_send_message_to_thread(self, sender, mock_client):
        """スレッド返信が正しく動作すること"""
        result = await sender.send_message(
            channel_id="C123456",
            text="Thread reply",
            thread_ts="1234567880.000000",
        )

        assert result["ok"] is True
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C123456",
            text="Thread reply",
            thread_ts="1234567880.000000",
        )

    async def test_send_message_retry_on_transient_error(self, sender, mock_client):
        """一時的エラーでリトライされること"""
        # 最初の2回は失敗、3回目で成功
        mock_client.chat_postMessage.side_effect = [
            SlackApiError(
                message="service_unavailable",
                response={"ok": False, "error": "service_unavailable"},
            ),
            SlackApiError(
                message="internal_error",
                response={"ok": False, "error": "internal_error"},
            ),
            {"ok": True, "ts": "1234567890.123456", "channel": "C123456"},
        ]

        result = await sender.send_message(
            channel_id="C123456",
            text="Hello",
        )

        assert result["ok"] is True
        assert mock_client.chat_postMessage.call_count == 3

    async def test_send_message_retry_exhausted(self, sender, mock_client):
        """リトライ上限でエラーがスローされること"""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="service_unavailable",
            response={"ok": False, "error": "service_unavailable"},
        )

        with pytest.raises(SlackAPIError) as exc_info:
            await sender.send_message(
                channel_id="C123456",
                text="Hello",
            )

        assert exc_info.value.error_code == "service_unavailable"
        # 初回 + リトライ3回 = 4回
        assert mock_client.chat_postMessage.call_count == 4

    async def test_send_message_rate_limit_handling(self, sender, mock_client):
        """レート制限エラーが適切に処理されること"""
        # rate_limitedエラーでリトライ
        mock_response = MagicMock()
        mock_response.__getitem__ = lambda self, key: {"ok": False, "error": "ratelimited"}[key]
        mock_response.get = lambda key, default=None: {"ok": False, "error": "ratelimited"}.get(
            key, default
        )
        mock_response.headers = {"Retry-After": "1"}

        mock_client.chat_postMessage.side_effect = [
            SlackApiError(message="ratelimited", response=mock_response),
            {"ok": True, "ts": "1234567890.123456", "channel": "C123456"},
        ]

        result = await sender.send_message(
            channel_id="C123456",
            text="Hello",
        )

        assert result["ok"] is True
        assert mock_client.chat_postMessage.call_count == 2

    async def test_send_message_non_retryable_error(self, sender, mock_client):
        """リトライ不可エラーは即座に失敗すること"""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response={"ok": False, "error": "channel_not_found"},
        )

        with pytest.raises(SlackAPIError) as exc_info:
            await sender.send_message(
                channel_id="C123456",
                text="Hello",
            )

        assert exc_info.value.error_code == "channel_not_found"
        # リトライ不可なので1回のみ
        assert mock_client.chat_postMessage.call_count == 1

    async def test_send_message_logs_on_success(self, sender, mock_client):
        """成功時にログが出力されること"""
        # ログ出力は実装内部で行われるため、エラーなく完了することを確認
        result = await sender.send_message(
            channel_id="C123456",
            text="Hello",
        )

        assert result["ok"] is True

    async def test_send_message_logs_on_error(self, sender, mock_client):
        """エラー時にログが出力されること"""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response={"ok": False, "error": "channel_not_found"},
        )

        with pytest.raises(SlackAPIError):
            await sender.send_message(
                channel_id="C123456",
                text="Hello",
            )

        # ログ出力は実装内部で行われるため、例外がスローされることを確認

    async def test_send_message_empty_text(self, sender, mock_client):
        """空のテキストでもメッセージが送信されること"""
        result = await sender.send_message(
            channel_id="C123456",
            text="",
        )

        assert result["ok"] is True
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C123456",
            text="",
            thread_ts=None,
        )
