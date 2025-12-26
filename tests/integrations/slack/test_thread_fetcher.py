"""ThreadHistoryFetcherのテスト"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from nyao.core.exceptions import SlackAPIError
from nyao.core.models import SlackMessage
from nyao.integrations.slack.thread_fetcher import ThreadHistoryFetcher


class TestThreadHistoryFetcher:
    """ThreadHistoryFetcherのテスト"""

    async def test_fetch_thread_messages_success(self, mock_web_client: AsyncMock) -> None:
        """スレッドメッセージ取得成功"""
        mock_web_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Parent message",
                    "ts": "1234567890.123456",
                },
                {
                    "type": "message",
                    "user": "U67890",
                    "text": "Reply 1",
                    "ts": "1234567890.654321",
                    "thread_ts": "1234567890.123456",
                },
            ],
        }
        mock_web_client.users_info.side_effect = [
            {"ok": True, "user": {"real_name": "User One", "name": "userone"}},
            {"ok": True, "user": {"real_name": "User Two", "name": "usertwo"}},
        ]

        fetcher = ThreadHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_thread_messages(
            channel_id="C12345",
            thread_ts="1234567890.123456",
        )

        assert len(messages) == 2
        assert all(isinstance(m, SlackMessage) for m in messages)
        mock_web_client.conversations_replies.assert_called_once_with(
            channel="C12345",
            ts="1234567890.123456",
            limit=100,
        )

    async def test_fetch_thread_messages_includes_bot(
        self, mock_web_client: AsyncMock, bot_user_id: str
    ) -> None:
        """Bot自身のメッセージも含む（コンテキスト理解に必要）"""
        mock_web_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "User message",
                    "ts": "1234567890.123456",
                },
                {
                    "type": "message",
                    "user": bot_user_id,
                    "text": "Bot reply",
                    "ts": "1234567890.654321",
                    "thread_ts": "1234567890.123456",
                    "bot_id": "B12345",
                },
            ],
        }
        mock_web_client.users_info.side_effect = [
            {"ok": True, "user": {"real_name": "User One", "name": "userone"}},
            {"ok": True, "user": {"real_name": "Bot", "name": "nyao"}},
        ]

        fetcher = ThreadHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_thread_messages(
            channel_id="C12345",
            thread_ts="1234567890.123456",
        )

        # Bot自身のメッセージも含まれる
        assert len(messages) == 2
        assert messages[1].text == "Bot reply"

    async def test_fetch_thread_messages_chronological_order(
        self, mock_web_client: AsyncMock
    ) -> None:
        """時系列順でメッセージを返す"""
        mock_web_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "First",
                    "ts": "1234567890.000001",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Second",
                    "ts": "1234567890.000002",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Third",
                    "ts": "1234567890.000003",
                },
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "User", "name": "user"},
        }

        fetcher = ThreadHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_thread_messages(
            channel_id="C12345",
            thread_ts="1234567890.000001",
        )

        assert len(messages) == 3
        assert messages[0].text == "First"
        assert messages[1].text == "Second"
        assert messages[2].text == "Third"

    async def test_fetch_thread_messages_converts_to_slack_message(
        self, mock_web_client: AsyncMock
    ) -> None:
        """メッセージがSlackMessageに正しく変換される"""
        mock_web_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Test message",
                    "ts": "1234567890.123456",
                    "thread_ts": "1234567890.123456",
                    "reactions": [
                        {"name": "thumbsup", "count": 1},
                        {"name": "heart", "count": 2},
                    ],
                    "reply_count": 5,
                },
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "name": "testuser"},
        }

        fetcher = ThreadHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_thread_messages(
            channel_id="C12345",
            thread_ts="1234567890.123456",
        )

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_id == "1234567890.123456"
        assert msg.channel_id == "C12345"
        assert msg.thread_ts == "1234567890.123456"
        assert msg.user_id == "U12345"
        assert msg.user_name == "Test User"
        assert msg.text == "Test message"
        assert isinstance(msg.timestamp, datetime)
        assert msg.reactions == ["thumbsup", "heart"]
        assert msg.reply_count == 5

    async def test_fetch_thread_messages_with_limit(self, mock_web_client: AsyncMock) -> None:
        """limit指定の動作"""
        mock_web_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [],
        }

        fetcher = ThreadHistoryFetcher(mock_web_client)
        await fetcher.fetch_thread_messages(
            channel_id="C12345",
            thread_ts="1234567890.123456",
            limit=50,
        )

        mock_web_client.conversations_replies.assert_called_once_with(
            channel="C12345",
            ts="1234567890.123456",
            limit=50,
        )

    async def test_fetch_thread_messages_api_error(self, mock_web_client: AsyncMock) -> None:
        """APIエラー時のSlackAPIError"""
        mock_web_client.conversations_replies.side_effect = SlackApiError(
            message="thread_not_found",
            response={"error": "thread_not_found"},
        )

        fetcher = ThreadHistoryFetcher(mock_web_client)

        with pytest.raises(SlackAPIError) as exc_info:
            await fetcher.fetch_thread_messages(
                channel_id="C12345",
                thread_ts="invalid_ts",
            )

        assert exc_info.value.error_code == "thread_not_found"

    async def test_fetch_thread_messages_user_name_cache(self, mock_web_client: AsyncMock) -> None:
        """ユーザー名がキャッシュされる"""
        mock_web_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Message 1",
                    "ts": "1234567890.000001",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Message 2",
                    "ts": "1234567890.000002",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Message 3",
                    "ts": "1234567890.000003",
                },
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "User", "name": "user"},
        }

        fetcher = ThreadHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_thread_messages(
            channel_id="C12345",
            thread_ts="1234567890.000001",
        )

        assert len(messages) == 3
        # 同じユーザーなので1回しかAPIを呼ばない
        assert mock_web_client.users_info.call_count == 1
