"""EventReceiverのテスト"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from nyao.core.models import SlackMessage
from nyao.integrations.slack.event_receiver import EventReceiver


class TestEventReceiver:
    """EventReceiverのテスト"""

    async def test_handle_message_event_success(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
        sample_message_event: dict,
    ) -> None:
        """通常メッセージの処理"""
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "name": "testuser"},
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        result = await receiver.handle_message_event(sample_message_event, say)

        assert result is not None
        assert isinstance(result, SlackMessage)
        assert result.text == "Hello, world!"
        assert result.channel_id == "C12345"
        assert result.user_id == "U12345"

    async def test_handle_message_event_thread_message(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
        sample_thread_message_event: dict,
    ) -> None:
        """スレッドメッセージの識別"""
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "name": "testuser"},
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        result = await receiver.handle_message_event(sample_thread_message_event, say)

        assert result is not None
        assert result.thread_ts == "1234567890.123456"
        assert result.text == "Thread reply!"

    async def test_handle_message_event_ignores_bot(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """Botメッセージの無視"""
        bot_message_event = {
            "type": "message",
            "channel": "C12345",
            "user": "U12345",
            "text": "Bot message",
            "ts": "1234567890.123456",
            "bot_id": "B12345",  # Botからのメッセージ
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        result = await receiver.handle_message_event(bot_message_event, say)

        assert result is None

    async def test_handle_message_event_ignores_system_message(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """システムメッセージの無視"""
        system_messages = [
            {"type": "message", "subtype": "channel_join", "channel": "C12345", "ts": "1"},
            {"type": "message", "subtype": "channel_leave", "channel": "C12345", "ts": "2"},
            {"type": "message", "subtype": "channel_topic", "channel": "C12345", "ts": "3"},
            {"type": "message", "subtype": "channel_purpose", "channel": "C12345", "ts": "4"},
        ]

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        for event in system_messages:
            result = await receiver.handle_message_event(event, say)
            assert result is None, f"Expected None for subtype: {event.get('subtype')}"

    async def test_handle_message_event_allows_file_share(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """file_share subtypeは処理する"""
        file_share_event = {
            "type": "message",
            "subtype": "file_share",
            "channel": "C12345",
            "user": "U12345",
            "text": "Shared a file",
            "ts": "1234567890.123456",
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "name": "testuser"},
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        result = await receiver.handle_message_event(file_share_event, say)

        assert result is not None
        assert result.text == "Shared a file"

    async def test_handle_message_event_converts_to_slack_message(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """イベントがSlackMessageに正しく変換される"""
        event = {
            "type": "message",
            "channel": "C12345",
            "user": "U12345",
            "text": "Test message",
            "ts": "1234567890.123456",
            "thread_ts": "1234567890.000001",
            "reactions": [
                {"name": "thumbsup", "count": 1},
            ],
        }
        mock_web_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "name": "testuser"},
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        result = await receiver.handle_message_event(event, say)

        assert result is not None
        assert result.message_id == "1234567890.123456"
        assert result.channel_id == "C12345"
        assert result.user_id == "U12345"
        assert result.user_name == "Test User"
        assert result.text == "Test message"
        assert result.thread_ts == "1234567890.000001"
        assert result.reactions == ["thumbsup"]
        assert isinstance(result.timestamp, datetime)

    async def test_handle_reaction_event_success(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
        sample_reaction_event: dict,
    ) -> None:
        """リアクションイベント処理"""
        receiver = EventReceiver(mock_web_client, bot_user_id)

        result = await receiver.handle_reaction_event(sample_reaction_event)

        assert result is not None
        assert result["user"] == "U12345"
        assert result["reaction"] == "thumbsup"
        assert result["channel"] == "C12345"
        assert result["message_ts"] == "1234567890.123456"

    async def test_handle_reaction_event_ignores_bot(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """Botリアクションの無視"""
        bot_reaction_event = {
            "type": "reaction_added",
            "user": bot_user_id,  # Bot自身のリアクション
            "reaction": "robot_face",
            "item": {
                "type": "message",
                "channel": "C12345",
                "ts": "1234567890.123456",
            },
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)

        result = await receiver.handle_reaction_event(bot_reaction_event)

        assert result is None

    async def test_handle_message_event_message_changed_ignored(
        self,
        mock_web_client: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """message_changed subtypeは無視される"""
        message_changed_event = {
            "type": "message",
            "subtype": "message_changed",
            "channel": "C12345",
            "ts": "1234567890.123456",
            "message": {
                "user": "U12345",
                "text": "Updated text",
            },
        }

        receiver = EventReceiver(mock_web_client, bot_user_id)
        say = MagicMock()

        result = await receiver.handle_message_event(message_changed_event, say)

        assert result is None
