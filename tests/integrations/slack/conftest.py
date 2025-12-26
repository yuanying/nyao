"""Slack連携テスト用共通フィクスチャ"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from nyao.core.models import SlackMessage


@pytest.fixture
def mock_web_client() -> AsyncMock:
    """モックWebClient"""
    client = AsyncMock()
    client.chat_postMessage = AsyncMock()
    client.conversations_replies = AsyncMock()
    client.conversations_history = AsyncMock()
    client.users_info = AsyncMock()
    client.auth_test = AsyncMock(return_value={"user_id": "U_BOT_ID"})
    return client


@pytest.fixture
def bot_user_id() -> str:
    """テスト用BotユーザーID"""
    return "U_BOT_ID"


@pytest.fixture
def sample_message_event() -> dict:
    """サンプルメッセージイベント"""
    return {
        "type": "message",
        "channel": "C12345",
        "user": "U12345",
        "text": "Hello, world!",
        "ts": "1234567890.123456",
    }


@pytest.fixture
def sample_thread_message_event() -> dict:
    """サンプルスレッドメッセージイベント"""
    return {
        "type": "message",
        "channel": "C12345",
        "user": "U12345",
        "text": "Thread reply!",
        "ts": "1234567890.654321",
        "thread_ts": "1234567890.123456",
    }


@pytest.fixture
def sample_reaction_event() -> dict:
    """サンプルリアクションイベント"""
    return {
        "type": "reaction_added",
        "user": "U12345",
        "reaction": "thumbsup",
        "item": {
            "type": "message",
            "channel": "C12345",
            "ts": "1234567890.123456",
        },
    }


@pytest.fixture
def sample_slack_message() -> SlackMessage:
    """サンプルSlackMessage"""
    return SlackMessage(
        message_id="1234567890.123456",
        channel_id="C12345",
        user_id="U12345",
        user_name="Test User",
        text="Hello, world!",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        reactions=[],
        reply_count=0,
    )
