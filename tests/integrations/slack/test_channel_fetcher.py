"""ChannelHistoryFetcherのテスト"""

from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from nyao.core.exceptions import SlackAPIError
from nyao.core.models import SlackMessage
from nyao.integrations.slack.channel_fetcher import ChannelHistoryFetcher


class TestChannelHistoryFetcher:
    """ChannelHistoryFetcherのテスト"""

    async def test_fetch_channel_messages_success(self, mock_web_client: AsyncMock) -> None:
        """チャンネルメッセージ取得成功"""
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Message 1",
                    "ts": "1234567890.000002",
                },
                {
                    "type": "message",
                    "user": "U67890",
                    "text": "Message 2",
                    "ts": "1234567890.000001",
                },
            ],
        }
        mock_web_client.users_info.side_effect = [
            {"ok": True, "user": {"real_name": "User One", "name": "userone"}},
            {"ok": True, "user": {"real_name": "User Two", "name": "usertwo"}},
        ]

        fetcher = ChannelHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_channel_messages(channel_id="C12345")

        assert len(messages) == 2
        assert all(isinstance(m, SlackMessage) for m in messages)
        mock_web_client.conversations_history.assert_called_once_with(
            channel="C12345",
            limit=100,
            oldest=None,
        )

    async def test_fetch_channel_messages_excludes_thread_replies(
        self, mock_web_client: AsyncMock
    ) -> None:
        """スレッド返信は除外される"""
        # Slack APIは新しい順にメッセージを返す
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U67890",
                    "text": "Normal message",
                    "ts": "1234567890.000003",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Thread reply (should be excluded)",
                    "ts": "1234567890.000002",
                    "thread_ts": "1234567890.000001",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Parent message (thread starter)",
                    "ts": "1234567890.000001",
                    "thread_ts": "1234567890.000001",
                    "reply_count": 3,
                },
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "User", "name": "user"},
        }

        fetcher = ChannelHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_channel_messages(channel_id="C12345")

        # スレッド返信は除外されるが、スレッド親と通常メッセージは含まれる（時系列順）
        assert len(messages) == 2
        assert messages[0].text == "Parent message (thread starter)"
        assert messages[1].text == "Normal message"

    async def test_fetch_channel_messages_includes_thread_parent(
        self, mock_web_client: AsyncMock
    ) -> None:
        """スレッド親メッセージは含まれる"""
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Thread parent",
                    "ts": "1234567890.000001",
                    "thread_ts": "1234567890.000001",
                    "reply_count": 5,
                },
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "User", "name": "user"},
        }

        fetcher = ChannelHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_channel_messages(channel_id="C12345")

        assert len(messages) == 1
        assert messages[0].text == "Thread parent"
        assert messages[0].reply_count == 5

    async def test_fetch_channel_messages_includes_bot(
        self, mock_web_client: AsyncMock, bot_user_id: str
    ) -> None:
        """Bot自身のメッセージも含む（コンテキスト理解に必要）"""
        # Slack APIは新しい順にメッセージを返す
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": bot_user_id,
                    "text": "Bot message",
                    "ts": "1234567890.000002",
                    "bot_id": "B12345",
                },
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "User message",
                    "ts": "1234567890.000001",
                },
            ],
        }
        mock_web_client.users_info.side_effect = [
            {"ok": True, "user": {"real_name": "Bot", "name": "nyao"}},
            {"ok": True, "user": {"real_name": "User", "name": "user"}},
        ]

        fetcher = ChannelHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_channel_messages(channel_id="C12345")

        # Bot自身のメッセージも含まれる（時系列順なのでBotは後ろ）
        assert len(messages) == 2
        assert messages[1].text == "Bot message"

    async def test_fetch_channel_messages_with_oldest(self, mock_web_client: AsyncMock) -> None:
        """oldest指定の動作"""
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [],
        }

        fetcher = ChannelHistoryFetcher(mock_web_client)
        await fetcher.fetch_channel_messages(
            channel_id="C12345",
            oldest=1234567890.0,
        )

        mock_web_client.conversations_history.assert_called_once_with(
            channel="C12345",
            limit=100,
            oldest="1234567890.0",
        )

    async def test_fetch_channel_messages_chronological_order(
        self, mock_web_client: AsyncMock
    ) -> None:
        """時系列順でメッセージを返す"""
        # Slack APIは新しい順に返すので、古い順に並べ替える
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Third",
                    "ts": "1234567890.000003",
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
                    "text": "First",
                    "ts": "1234567890.000001",
                },
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "User", "name": "user"},
        }

        fetcher = ChannelHistoryFetcher(mock_web_client)
        messages = await fetcher.fetch_channel_messages(channel_id="C12345")

        assert len(messages) == 3
        assert messages[0].text == "First"
        assert messages[1].text == "Second"
        assert messages[2].text == "Third"

    async def test_fetch_channel_messages_api_error(self, mock_web_client: AsyncMock) -> None:
        """APIエラー時のSlackAPIError"""
        mock_web_client.conversations_history.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        fetcher = ChannelHistoryFetcher(mock_web_client)

        with pytest.raises(SlackAPIError) as exc_info:
            await fetcher.fetch_channel_messages(channel_id="INVALID")

        assert exc_info.value.error_code == "channel_not_found"

    async def test_fetch_channel_messages_with_limit(self, mock_web_client: AsyncMock) -> None:
        """limit指定の動作"""
        mock_web_client.conversations_history.return_value = {
            "ok": True,
            "messages": [],
        }

        fetcher = ChannelHistoryFetcher(mock_web_client)
        await fetcher.fetch_channel_messages(
            channel_id="C12345",
            limit=50,
        )

        mock_web_client.conversations_history.assert_called_once_with(
            channel="C12345",
            limit=50,
            oldest=None,
        )
