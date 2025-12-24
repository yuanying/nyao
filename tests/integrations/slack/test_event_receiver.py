"""EventReceiver と UserInfoCache のテスト"""

import time
from unittest.mock import AsyncMock

import pytest

from nyao.core.exceptions import SlackAPIError
from nyao.core.models import SlackMessage
from nyao.integrations.slack.event_receiver import EventReceiver, UserInfoCache


class TestUserInfoCache:
    """UserInfoCache のテスト"""

    def test_set_and_get(self):
        """キャッシュに保存・取得できること"""
        cache = UserInfoCache(ttl_seconds=3600)
        cache.set("U123", "test_user")

        assert cache.get("U123") == "test_user"

    def test_get_returns_none_on_cache_miss(self):
        """キャッシュミスでNoneを返すこと"""
        cache = UserInfoCache(ttl_seconds=3600)

        assert cache.get("U123") is None

    def test_cache_ttl_expiry(self):
        """TTL後にキャッシュが期限切れになること"""
        cache = UserInfoCache(ttl_seconds=1)
        cache.set("U123", "test_user")

        # 1秒待機して期限切れにする
        time.sleep(1.1)

        assert cache.get("U123") is None

    def test_clear(self):
        """キャッシュをクリアできること"""
        cache = UserInfoCache(ttl_seconds=3600)
        cache.set("U123", "test_user")
        cache.set("U456", "another_user")

        cache.clear()

        assert cache.get("U123") is None
        assert cache.get("U456") is None


class TestEventReceiver:
    """EventReceiver のテスト"""

    @pytest.fixture
    def mock_client(self):
        """AsyncWebClient のモック"""
        client = AsyncMock()
        client.users_info = AsyncMock(
            return_value={"ok": True, "user": {"profile": {"display_name": "Test User"}}}
        )
        return client

    @pytest.fixture
    def receiver(self, mock_client):
        """EventReceiver インスタンス"""
        return EventReceiver(
            client=mock_client,
            monitored_channels=["C123456", "C789012"],
            bot_user_id="UBOT123",
        )

    def test_is_monitored_channel_returns_true(self, receiver):
        """監視対象チャンネルでTrueを返すこと"""
        assert receiver.is_monitored_channel("C123456") is True
        assert receiver.is_monitored_channel("C789012") is True

    def test_is_monitored_channel_returns_false(self, receiver):
        """監視対象外チャンネルでFalseを返すこと"""
        assert receiver.is_monitored_channel("C999999") is False

    def test_is_bot_message_returns_true_for_bot_id(self, receiver):
        """bot_idがあるメッセージでTrueを返すこと"""
        event = {"user": "U123", "bot_id": "B123"}
        assert receiver.is_bot_message(event) is True

    def test_is_bot_message_returns_true_for_bot_user_id(self, receiver):
        """Bot自身のユーザーIDでTrueを返すこと"""
        event = {"user": "UBOT123"}
        assert receiver.is_bot_message(event) is True

    def test_is_bot_message_returns_false_for_user(self, receiver):
        """通常ユーザーメッセージでFalseを返すこと"""
        event = {"user": "U123"}
        assert receiver.is_bot_message(event) is False

    def test_is_system_message_returns_true_for_channel_join(self, receiver):
        """channel_joinでTrueを返すこと"""
        event = {"subtype": "channel_join"}
        assert receiver.is_system_message(event) is True

    def test_is_system_message_returns_true_for_channel_leave(self, receiver):
        """channel_leaveでTrueを返すこと"""
        event = {"subtype": "channel_leave"}
        assert receiver.is_system_message(event) is True

    def test_is_system_message_returns_true_for_channel_topic(self, receiver):
        """channel_topicでTrueを返すこと"""
        event = {"subtype": "channel_topic"}
        assert receiver.is_system_message(event) is True

    def test_is_system_message_returns_true_for_channel_purpose(self, receiver):
        """channel_purposeでTrueを返すこと"""
        event = {"subtype": "channel_purpose"}
        assert receiver.is_system_message(event) is True

    def test_is_system_message_returns_false_for_normal_message(self, receiver):
        """通常メッセージでFalseを返すこと"""
        event = {"text": "Hello"}
        assert receiver.is_system_message(event) is False

    async def test_get_user_name_with_cache_miss(self, receiver, mock_client):
        """キャッシュミス時にAPIを呼ぶこと"""
        user_name = await receiver.get_user_name("U123")

        assert user_name == "Test User"
        mock_client.users_info.assert_called_once_with(user="U123")

    async def test_get_user_name_with_cache_hit(self, receiver, mock_client):
        """キャッシュヒット時にAPIを呼ばないこと"""
        # 1回目はAPIを呼ぶ
        await receiver.get_user_name("U123")
        mock_client.users_info.reset_mock()

        # 2回目はキャッシュから取得
        user_name = await receiver.get_user_name("U123")

        assert user_name == "Test User"
        mock_client.users_info.assert_not_called()

    async def test_get_user_name_fallback_to_real_name(self, receiver, mock_client):
        """display_nameが空の場合real_nameを使用すること"""
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"profile": {"display_name": "", "real_name": "Real Name"}},
        }

        user_name = await receiver.get_user_name("U123")

        assert user_name == "Real Name"

    async def test_get_user_name_fallback_to_user_id(self, receiver, mock_client):
        """名前が取得できない場合user_idを使用すること"""
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"profile": {"display_name": "", "real_name": ""}},
        }

        user_name = await receiver.get_user_name("U123")

        assert user_name == "U123"

    async def test_get_user_name_api_error(self, receiver, mock_client):
        """API エラー時に SlackAPIError をスローすること"""
        from slack_sdk.errors import SlackApiError

        mock_client.users_info.side_effect = SlackApiError(
            message="user_not_found",
            response={"ok": False, "error": "user_not_found"},
        )

        with pytest.raises(SlackAPIError) as exc_info:
            await receiver.get_user_name("U123")

        assert exc_info.value.error_code == "user_not_found"

    async def test_convert_to_slack_message_success(self, receiver):
        """イベントがSlackMessageに正しく変換されること"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "U123",
            "text": "Hello, world!",
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is not None
        assert message.message_id == "1234567890.123456"
        assert message.channel_id == "C123456"
        assert message.user_id == "U123"
        assert message.user_name == "Test User"
        assert message.text == "Hello, world!"
        assert message.thread_ts is None

    async def test_convert_to_slack_message_with_thread(self, receiver):
        """スレッドメッセージが正しく識別されること"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "U123",
            "text": "Thread reply",
            "thread_ts": "1234567880.000000",
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is not None
        assert message.thread_ts == "1234567880.000000"

    async def test_convert_to_slack_message_with_reactions(self, receiver):
        """リアクション付きメッセージが正しく変換されること"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "U123",
            "text": "Hello",
            "reactions": [{"name": "thumbsup", "count": 2}, {"name": "heart", "count": 1}],
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is not None
        assert "thumbsup" in message.reactions
        assert "heart" in message.reactions

    async def test_convert_to_slack_message_with_reply_count(self, receiver):
        """返信数が正しく変換されること"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "U123",
            "text": "Hello",
            "reply_count": 5,
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is not None
        assert message.reply_count == 5

    async def test_convert_to_slack_message_returns_none_for_unmonitored_channel(self, receiver):
        """監視対象外チャンネルのメッセージはNoneを返すこと"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C999999",
            "user": "U123",
            "text": "Hello",
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is None

    async def test_convert_to_slack_message_returns_none_for_bot_message(self, receiver):
        """Bot自身のメッセージはNoneを返すこと"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "UBOT123",
            "text": "Bot message",
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is None

    async def test_convert_to_slack_message_returns_none_for_system_message(self, receiver):
        """システムメッセージはNoneを返すこと"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "U123",
            "text": "joined the channel",
            "subtype": "channel_join",
        }

        message = await receiver.convert_to_slack_message(event)

        assert message is None

    async def test_handle_message_event_success(self, receiver):
        """メッセージイベントが正しく処理されること"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "U123",
            "text": "Hello",
        }
        say = AsyncMock()

        message = await receiver.handle_message_event(event, say)

        assert message is not None
        assert isinstance(message, SlackMessage)

    async def test_handle_message_event_filters_bot(self, receiver):
        """Bot自身のメッセージが無視されること"""
        event = {
            "ts": "1234567890.123456",
            "channel": "C123456",
            "user": "UBOT123",
            "text": "Bot message",
        }
        say = AsyncMock()

        message = await receiver.handle_message_event(event, say)

        assert message is None

    async def test_handle_reaction_event_success(self, receiver):
        """リアクションイベントが正しく処理されること"""
        event = {
            "type": "reaction_added",
            "user": "U123",
            "reaction": "thumbsup",
            "item": {"type": "message", "channel": "C123456", "ts": "1234567890.123456"},
        }

        result = await receiver.handle_reaction_event(event)

        assert result is not None
        assert result["reaction"] == "thumbsup"
        assert result["channel_id"] == "C123456"
        assert result["message_ts"] == "1234567890.123456"

    async def test_handle_reaction_event_returns_none_for_unmonitored_channel(self, receiver):
        """監視対象外チャンネルのリアクションはNoneを返すこと"""
        event = {
            "type": "reaction_added",
            "user": "U123",
            "reaction": "thumbsup",
            "item": {"type": "message", "channel": "C999999", "ts": "1234567890.123456"},
        }

        result = await receiver.handle_reaction_event(event)

        assert result is None
