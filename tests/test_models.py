"""データモデルのテストコード"""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from nyao.core.models import (
    ConversationContext,
    LLMResponse,
    ResponseDecision,
    SlackMessage,
)


class TestSlackMessage:
    """SlackMessageモデルのテスト"""

    def test_create_slack_message_with_required_fields(self):
        """必須フィールドのみでSlackMessageを作成できること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        assert msg.message_id == "1234567890.123456"
        assert msg.channel_id == "C123456"
        assert msg.user_id == "U789012"
        assert msg.user_name == "test_user"
        assert msg.text == "Hello, world!"
        assert msg.timestamp == datetime(2024, 12, 21, 10, 30, 45)
        assert msg.thread_ts is None
        assert msg.reactions == []
        assert msg.reply_count == 0

    def test_slack_message_with_optional_fields(self):
        """オプショナルフィールドを含むSlackMessageを作成できること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            thread_ts="1234567890.000000",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
            reactions=["thumbsup", "heart"],
            reply_count=3,
        )

        assert msg.thread_ts == "1234567890.000000"
        assert msg.reactions == ["thumbsup", "heart"]
        assert msg.reply_count == 3

    def test_slack_message_with_defaults(self):
        """デフォルト値が正しく設定されること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        assert msg.reactions == []
        assert msg.reply_count == 0

    def test_slack_message_json_serialization(self):
        """SlackMessageがJSON形式にシリアライズできること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        assert data["message_id"] == "1234567890.123456"
        assert data["channel_id"] == "C123456"
        assert data["user_id"] == "U789012"
        assert data["text"] == "Hello, world!"

    def test_slack_message_json_deserialization(self):
        """JSON形式からSlackMessageをデシリアライズできること"""
        json_data = {
            "message_id": "1234567890.123456",
            "channel_id": "C123456",
            "user_id": "U789012",
            "user_name": "test_user",
            "text": "Hello, world!",
            "timestamp": "2024-12-21T10:30:45",
        }

        msg = SlackMessage.model_validate(json_data)

        assert msg.message_id == "1234567890.123456"
        assert msg.channel_id == "C123456"
        assert msg.user_id == "U789012"
        assert msg.user_name == "test_user"
        assert msg.text == "Hello, world!"

    def test_slack_message_datetime_iso8601_format(self):
        """datetime型がISO8601形式にシリアライズされること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        # ISO8601形式（YYYY-MM-DDTHH:MM:SS）であることを確認
        assert data["timestamp"] == "2024-12-21T10:30:45"

    def test_slack_message_invalid_type_raises_error(self):
        """不正な型でバリデーションエラーが発生すること"""
        with pytest.raises(ValidationError):
            SlackMessage(
                message_id="1234567890.123456",
                channel_id="C123456",
                user_id="U789012",
                user_name="test_user",
                text="Hello, world!",
                timestamp="invalid_datetime",  # type: ignore  # 不正な型
            )


class TestConversationContext:
    """ConversationContextモデルのテスト"""

    def test_create_conversation_context(self):
        """ConversationContextを作成できること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        context = ConversationContext(
            channel_id="C123456",
            messages=[msg],
            last_updated=datetime(2024, 12, 21, 10, 30, 45),
        )

        assert context.channel_id == "C123456"
        assert context.thread_ts is None
        assert len(context.messages) == 1
        assert context.messages[0] == msg
        assert context.last_updated == datetime(2024, 12, 21, 10, 30, 45)

    def test_add_message_to_context(self):
        """add_message()でメッセージを追加できること"""
        msg1 = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="First message",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        context = ConversationContext(
            channel_id="C123456",
            messages=[msg1],
            last_updated=datetime(2024, 12, 21, 10, 30, 45),
        )

        msg2 = SlackMessage(
            message_id="1234567890.123457",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Second message",
            timestamp=datetime(2024, 12, 21, 10, 31, 0),
        )

        context.add_message(msg2)

        assert len(context.messages) == 2
        assert context.messages[1] == msg2

    def test_add_message_updates_last_updated(self):
        """add_message()がlast_updatedを更新すること"""
        msg1 = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="First message",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        context = ConversationContext(
            channel_id="C123456",
            messages=[msg1],
            last_updated=datetime(2024, 12, 21, 10, 30, 45),
        )

        original_last_updated = context.last_updated

        msg2 = SlackMessage(
            message_id="1234567890.123457",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Second message",
            timestamp=datetime(2024, 12, 21, 10, 31, 0),
        )

        context.add_message(msg2)

        # last_updatedが更新されていることを確認
        assert context.last_updated > original_last_updated

    def test_get_recent_messages_with_limit(self):
        """get_recent_messages()で直近のメッセージを取得できること"""
        messages = [
            SlackMessage(
                message_id=f"123456789{i}.123456",
                channel_id="C123456",
                user_id="U789012",
                user_name="test_user",
                text=f"Message {i}",
                timestamp=datetime(2024, 12, 21, 10, 30, i),
            )
            for i in range(10)
        ]

        context = ConversationContext(
            channel_id="C123456",
            messages=messages,
            last_updated=datetime(2024, 12, 21, 10, 30, 45),
        )

        recent = context.get_recent_messages(3)

        assert len(recent) == 3
        assert recent[0].text == "Message 7"
        assert recent[1].text == "Message 8"
        assert recent[2].text == "Message 9"

    def test_get_recent_messages_exceeds_available(self):
        """get_recent_messages()で利用可能なメッセージ数を超える取得をしても問題ないこと"""
        messages = [
            SlackMessage(
                message_id=f"123456789{i}.123456",
                channel_id="C123456",
                user_id="U789012",
                user_name="test_user",
                text=f"Message {i}",
                timestamp=datetime(2024, 12, 21, 10, 30, i),
            )
            for i in range(3)
        ]

        context = ConversationContext(
            channel_id="C123456",
            messages=messages,
            last_updated=datetime(2024, 12, 21, 10, 30, 45),
        )

        recent = context.get_recent_messages(10)

        # すべてのメッセージが取得される
        assert len(recent) == 3

    def test_conversation_context_json_serialization(self):
        """ConversationContextがJSON形式にシリアライズできること"""
        msg = SlackMessage(
            message_id="1234567890.123456",
            channel_id="C123456",
            user_id="U789012",
            user_name="test_user",
            text="Hello, world!",
            timestamp=datetime(2024, 12, 21, 10, 30, 45),
        )

        context = ConversationContext(
            channel_id="C123456",
            messages=[msg],
            last_updated=datetime(2024, 12, 21, 10, 30, 45),
        )

        json_str = context.model_dump_json()
        data = json.loads(json_str)

        assert data["channel_id"] == "C123456"
        assert len(data["messages"]) == 1

    def test_conversation_context_json_deserialization(self):
        """JSON形式からConversationContextをデシリアライズできること"""
        json_data = {
            "channel_id": "C123456",
            "thread_ts": None,
            "messages": [
                {
                    "message_id": "1234567890.123456",
                    "channel_id": "C123456",
                    "thread_ts": None,
                    "user_id": "U789012",
                    "user_name": "test_user",
                    "text": "Hello, world!",
                    "timestamp": "2024-12-21T10:30:45",
                    "reactions": [],
                    "reply_count": 0,
                }
            ],
            "last_updated": "2024-12-21T10:30:45",
        }

        context = ConversationContext.model_validate(json_data)

        assert context.channel_id == "C123456"
        assert len(context.messages) == 1
        assert context.messages[0].text == "Hello, world!"


class TestResponseDecision:
    """ResponseDecisionモデルのテスト"""

    def test_create_response_decision(self):
        """ResponseDecisionを作成できること"""
        decision = ResponseDecision(
            should_respond=True,
            reason="No responses in 60 seconds",
            confidence=0.8,
        )

        assert decision.should_respond is True
        assert decision.reason == "No responses in 60 seconds"
        assert decision.confidence == 0.8
        assert decision.suggested_delay_minutes is None

    def test_response_decision_with_optional_delay(self):
        """オプショナルフィールドsuggested_delay_minutesを設定できること"""
        decision = ResponseDecision(
            should_respond=True,
            reason="No responses in 60 seconds",
            confidence=0.8,
            suggested_delay_minutes=5,
        )

        assert decision.suggested_delay_minutes == 5

    def test_confidence_range_validation(self):
        """confidenceが0.0-1.0の範囲内で正しく設定されること"""
        # 0.0
        decision_min = ResponseDecision(should_respond=True, reason="Test", confidence=0.0)
        assert decision_min.confidence == 0.0

        # 1.0
        decision_max = ResponseDecision(should_respond=True, reason="Test", confidence=1.0)
        assert decision_max.confidence == 1.0

        # 0.5
        decision_mid = ResponseDecision(should_respond=True, reason="Test", confidence=0.5)
        assert decision_mid.confidence == 0.5

    def test_confidence_below_range_raises_error(self):
        """confidenceが0.0未満でバリデーションエラーが発生すること"""
        with pytest.raises(ValidationError) as exc_info:
            ResponseDecision(
                should_respond=True,
                reason="Test",
                confidence=-0.1,
            )

        assert "confidence must be between 0.0 and 1.0" in str(exc_info.value)

    def test_confidence_above_range_raises_error(self):
        """confidenceが1.0を超えるとバリデーションエラーが発生すること"""
        with pytest.raises(ValidationError) as exc_info:
            ResponseDecision(
                should_respond=True,
                reason="Test",
                confidence=1.1,
            )

        assert "confidence must be between 0.0 and 1.0" in str(exc_info.value)

    def test_response_decision_json_serialization(self):
        """ResponseDecisionがJSON形式にシリアライズできること"""
        decision = ResponseDecision(
            should_respond=True,
            reason="No responses in 60 seconds",
            confidence=0.8,
        )

        json_str = decision.model_dump_json()
        data = json.loads(json_str)

        assert data["should_respond"] is True
        assert data["reason"] == "No responses in 60 seconds"
        assert data["confidence"] == 0.8
        assert data["suggested_delay_minutes"] is None


class TestLLMResponse:
    """LLMResponseモデルのテスト"""

    def test_create_llm_response(self):
        """LLMResponseを作成できること"""
        response = LLMResponse(
            content="This is a generated response.",
            model="openai/gpt-4o",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            finish_reason="stop",
        )

        assert response.content == "This is a generated response."
        assert response.model == "openai/gpt-4o"
        assert response.usage == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        assert response.finish_reason == "stop"

    def test_llm_response_json_serialization(self):
        """LLMResponseがJSON形式にシリアライズできること"""
        response = LLMResponse(
            content="This is a generated response.",
            model="openai/gpt-4o",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            finish_reason="stop",
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert data["content"] == "This is a generated response."
        assert data["model"] == "openai/gpt-4o"
        assert data["usage"]["prompt_tokens"] == 100
        assert data["finish_reason"] == "stop"

    def test_llm_response_json_deserialization(self):
        """JSON形式からLLMResponseをデシリアライズできること"""
        json_data = {
            "content": "This is a generated response.",
            "model": "openai/gpt-4o",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            "finish_reason": "stop",
        }

        response = LLMResponse.model_validate(json_data)

        assert response.content == "This is a generated response."
        assert response.model == "openai/gpt-4o"
        assert response.usage["prompt_tokens"] == 100

    def test_llm_response_invalid_usage_type_raises_error(self):
        """usageフィールドが不正な型でバリデーションエラーが発生すること"""
        with pytest.raises(ValidationError):
            LLMResponse(
                content="This is a generated response.",
                model="openai/gpt-4o",
                usage="invalid_usage",  # type: ignore  # 不正な型（辞書でない）
                finish_reason="stop",
            )
