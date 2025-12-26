"""プロンプト管理のテスト

PromptManagerクラスのテストを行います。
"""

from datetime import UTC, datetime

import pytest

from nyao.core.models import ConversationContext, SlackMessage
from nyao.integrations.llm.prompts import PromptManager


class TestPromptManagerInit:
    """PromptManager初期化のテスト"""

    def test_init_with_persona(self) -> None:
        """ペルソナを指定して初期化できること"""
        persona = "にゃおは友達のように接するチャットボットです"
        manager = PromptManager(persona=persona)

        assert manager.persona == persona

    def test_init_with_default_persona(self) -> None:
        """デフォルトペルソナで初期化できること"""
        manager = PromptManager()

        assert manager.persona is not None
        assert len(manager.persona) > 0


class TestBuildShouldRespondPrompt:
    """build_should_respond_promptのテスト"""

    @pytest.fixture
    def manager(self) -> PromptManager:
        """テスト用PromptManager"""
        return PromptManager(persona="テスト用ペルソナ")

    @pytest.fixture
    def sample_message(self) -> SlackMessage:
        """テスト用SlackMessage"""
        return SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="今日は良い天気ですね！",
            timestamp=datetime.now(UTC),
            reactions=["thumbsup"],
            reply_count=0,
        )

    def test_prompt_contains_message_text(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトにメッセージ本文が含まれること"""
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=1,
            reply_count=0,
        )

        assert sample_message.text in prompt

    def test_prompt_contains_user_name(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトにユーザー名が含まれること"""
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=1,
            reply_count=0,
        )

        assert sample_message.user_name in prompt

    def test_prompt_contains_elapsed_time(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトに経過時間が含まれること"""
        elapsed_seconds = 600
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=elapsed_seconds,
            reaction_count=1,
            reply_count=0,
        )

        # 分単位（10分）が含まれることを確認
        assert "10" in prompt or "600" in prompt

    def test_prompt_contains_reaction_count(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトにリアクション数が含まれること"""
        reaction_count = 3
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=reaction_count,
            reply_count=0,
        )

        assert str(reaction_count) in prompt

    def test_prompt_contains_reply_count(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトに返信数が含まれること"""
        reply_count = 2
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=0,
            reply_count=reply_count,
        )

        assert str(reply_count) in prompt

    def test_prompt_contains_judgment_criteria(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトに判定基準が含まれること"""
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=0,
            reply_count=0,
        )

        # 判定基準が含まれていることを確認
        assert "判定基準" in prompt
        assert "応答すべき場合" in prompt
        assert "応答すべきでない場合" in prompt

    def test_prompt_requests_confidence(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """プロンプトが確信度を要求すること"""
        prompt = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=0,
            reply_count=0,
        )

        assert "確信度" in prompt


class TestBuildResponseGenerationPrompt:
    """build_response_generation_promptのテスト"""

    @pytest.fixture
    def manager(self) -> PromptManager:
        """テスト用PromptManager"""
        return PromptManager(persona="にゃおは友達のように接するチャットボットです")

    @pytest.fixture
    def sample_message(self) -> SlackMessage:
        """テスト用SlackMessage"""
        return SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="今日のランチ何食べよう？",
            timestamp=datetime.now(UTC),
        )

    @pytest.fixture
    def sample_context(self, sample_message: SlackMessage) -> ConversationContext:
        """テスト用ConversationContext"""
        past_message = SlackMessage(
            message_id="msg-000",
            channel_id="C12345678",
            user_id="U87654321",
            user_name="otheruser",
            text="おはよう！",
            timestamp=datetime.now(UTC),
        )
        context = ConversationContext(
            channel_id="C12345678",
            last_updated=datetime.now(UTC),
            messages=[past_message, sample_message],
        )
        return context

    def test_prompt_contains_persona(
        self,
        manager: PromptManager,
        sample_message: SlackMessage,
        sample_context: ConversationContext,
    ) -> None:
        """プロンプトにペルソナが含まれること"""
        prompt = manager.build_response_generation_prompt(
            message=sample_message,
            context=sample_context,
        )

        assert manager.persona in prompt

    def test_prompt_contains_target_message(
        self,
        manager: PromptManager,
        sample_message: SlackMessage,
        sample_context: ConversationContext,
    ) -> None:
        """プロンプトに返信対象メッセージが含まれること"""
        prompt = manager.build_response_generation_prompt(
            message=sample_message,
            context=sample_context,
        )

        assert sample_message.text in prompt
        assert sample_message.user_name in prompt

    def test_prompt_contains_context_messages(
        self,
        manager: PromptManager,
        sample_message: SlackMessage,
        sample_context: ConversationContext,
    ) -> None:
        """プロンプトにコンテキストメッセージが含まれること"""
        prompt = manager.build_response_generation_prompt(
            message=sample_message,
            context=sample_context,
        )

        # コンテキストの過去メッセージも含まれること
        assert "おはよう" in prompt

    def test_prompt_without_context(
        self, manager: PromptManager, sample_message: SlackMessage
    ) -> None:
        """コンテキストなしでもプロンプトが構築できること"""
        prompt = manager.build_response_generation_prompt(
            message=sample_message,
            context=None,
        )

        assert sample_message.text in prompt
        assert manager.persona in prompt
