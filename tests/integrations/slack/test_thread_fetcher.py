"""ThreadHistoryFetcher のテスト"""

from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from nyao.core.exceptions import SlackAPIError
from nyao.core.models import SlackMessage
from nyao.integrations.slack.event_receiver import EventReceiver
from nyao.integrations.slack.thread_fetcher import ThreadHistoryFetcher


class TestThreadHistoryFetcher:
    """ThreadHistoryFetcher のテスト"""

    @pytest.fixture
    def mock_client(self):
        """AsyncWebClient のモック"""
        client = AsyncMock()
        client.users_info = AsyncMock(
            return_value={"ok": True, "user": {"profile": {"display_name": "Test User"}}}
        )
        return client

    @pytest.fixture
    def event_receiver(self, mock_client):
        """EventReceiver インスタンス"""
        return EventReceiver(
            client=mock_client,
            monitored_channels=["C123456", "C789012"],
            bot_user_id="UBOT123",
        )

    @pytest.fixture
    def fetcher(self, mock_client, event_receiver):
        """ThreadHistoryFetcher インスタンス"""
        return ThreadHistoryFetcher(
            client=mock_client,
            event_receiver=event_receiver,
        )

    async def test_fetch_thread_messages_success(self, fetcher, mock_client):
        """スレッド履歴が正しく取得されること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"ts": "1234567880.000000", "user": "U123", "text": "Parent message"},
                    {"ts": "1234567890.123456", "user": "U456", "text": "Reply 1"},
                    {"ts": "1234567900.123456", "user": "U789", "text": "Reply 2"},
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
        )

        assert len(messages) == 3
        assert all(isinstance(m, SlackMessage) for m in messages)
        mock_client.conversations_replies.assert_called_once_with(
            channel="C123456",
            ts="1234567880.000000",
            limit=100,
        )

    async def test_fetch_thread_messages_chronological_order(self, fetcher, mock_client):
        """メッセージが時系列順に並んでいること"""
        # APIが逆順で返す場合をシミュレート
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"ts": "1234567900.000000", "user": "U123", "text": "Third"},
                    {"ts": "1234567880.000000", "user": "U123", "text": "First"},
                    {"ts": "1234567890.000000", "user": "U123", "text": "Second"},
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
        )

        # 時系列順（古い順）にソートされていること
        assert messages[0].text == "First"
        assert messages[1].text == "Second"
        assert messages[2].text == "Third"

    async def test_fetch_thread_messages_excludes_bot(self, fetcher, mock_client):
        """Bot自身のメッセージが除外されること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"ts": "1234567880.000000", "user": "U123", "text": "User message"},
                    {"ts": "1234567890.000000", "user": "UBOT123", "text": "Bot message"},
                    {"ts": "1234567900.000000", "user": "U456", "text": "Another user"},
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
            include_bot_messages=False,
        )

        assert len(messages) == 2
        assert all(m.user_id != "UBOT123" for m in messages)

    async def test_fetch_thread_messages_includes_bot_when_specified(self, fetcher, mock_client):
        """オプションでBotメッセージを含められること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"ts": "1234567880.000000", "user": "U123", "text": "User message"},
                    {"ts": "1234567890.000000", "user": "UBOT123", "text": "Bot message"},
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
            include_bot_messages=True,
        )

        assert len(messages) == 2

    async def test_fetch_thread_messages_respects_limit(self, fetcher, mock_client):
        """limit引数が正しく適用されること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"ts": "1234567880.000000", "user": "U123", "text": "Message 1"},
                ],
            }
        )

        await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
            limit=50,
        )

        mock_client.conversations_replies.assert_called_once_with(
            channel="C123456",
            ts="1234567880.000000",
            limit=50,
        )

    async def test_fetch_thread_messages_api_error(self, fetcher, mock_client):
        """API エラー時に適切な例外がスローされること"""
        mock_client.conversations_replies = AsyncMock(
            side_effect=SlackApiError(
                message="thread_not_found",
                response={"ok": False, "error": "thread_not_found"},
            )
        )

        with pytest.raises(SlackAPIError) as exc_info:
            await fetcher.fetch_thread_messages(
                channel_id="C123456",
                thread_ts="1234567880.000000",
            )

        assert exc_info.value.error_code == "thread_not_found"

    async def test_fetch_thread_messages_empty_thread(self, fetcher, mock_client):
        """空のスレッドで空リストが返ること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
        )

        assert messages == []

    async def test_convert_message_with_reactions(self, fetcher, mock_client):
        """リアクション付きメッセージが正しく変換されること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {
                        "ts": "1234567880.000000",
                        "user": "U123",
                        "text": "Message with reactions",
                        "reactions": [
                            {"name": "thumbsup", "count": 2},
                            {"name": "heart", "count": 1},
                        ],
                    },
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
        )

        assert len(messages) == 1
        assert "thumbsup" in messages[0].reactions
        assert "heart" in messages[0].reactions

    async def test_fetch_thread_messages_with_reply_count(self, fetcher, mock_client):
        """返信数が正しく変換されること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {
                        "ts": "1234567880.000000",
                        "user": "U123",
                        "text": "Parent message",
                        "reply_count": 5,
                    },
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
        )

        assert len(messages) == 1
        assert messages[0].reply_count == 5

    async def test_fetch_thread_messages_excludes_bot_id(self, fetcher, mock_client):
        """bot_id付きメッセージも除外されること"""
        mock_client.conversations_replies = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"ts": "1234567880.000000", "user": "U123", "text": "User message"},
                    {
                        "ts": "1234567890.000000",
                        "user": "U999",
                        "bot_id": "B123",
                        "text": "Bot message",
                    },
                ],
            }
        )

        messages = await fetcher.fetch_thread_messages(
            channel_id="C123456",
            thread_ts="1234567880.000000",
            include_bot_messages=False,
        )

        assert len(messages) == 1
        assert messages[0].text == "User message"
