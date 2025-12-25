"""PromptManagerのテスト"""

from datetime import UTC, datetime

import pytest

from nyao.core.models import ConversationContext, SlackMessage
from nyao.integrations.llm.prompts import PromptManager


class TestPromptManagerInit:
    """PromptManagerの初期化テスト"""

    def test_init_with_persona(self):
        """ペルソナで初期化できること"""
        persona = "友達のようなカジュアルな口調で話す"
        manager = PromptManager(persona=persona)
        assert manager.persona == persona

    def test_from_settings_factory(self, tmp_path, monkeypatch):
        """from_settingsファクトリメソッドが動作すること"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
slack:
  channel_ids:
    - C1234567890
litellm:
  model_id: openai/gpt-4o
bot:
  persona: テスト用ペルソナ
""")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        # 設定をリロード
        from nyao.config.settings import reload_settings

        settings = reload_settings()

        manager = PromptManager.from_settings(settings)
        assert manager.persona == "テスト用ペルソナ"


class TestBuildShouldRespondPrompt:
    """応答判定プロンプト構築テスト"""

    @pytest.fixture
    def manager(self):
        """PromptManagerのフィクスチャ"""
        return PromptManager(persona="友達のようなカジュアルな口調で話す")

    @pytest.fixture
    def sample_message(self):
        """テスト用のSlackMessageフィクスチャ"""
        return SlackMessage(
            message_id="1234567890.123456",
            channel_id="C1234567890",
            user_id="U1234567890",
            user_name="testuser",
            text="今日はいい天気ですね",
            timestamp=datetime.now(UTC),
            reactions=[],
            reply_count=0,
        )

    def test_build_should_respond_prompt_format(self, manager, sample_message):
        """OpenAI形式のメッセージリストが返されること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        assert isinstance(result, list)
        assert len(result) >= 1
        for msg in result:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("system", "user", "assistant")

    def test_build_should_respond_prompt_contains_message_info(self, manager, sample_message):
        """メッセージ情報がプロンプトに含まれること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        # プロンプト全体のテキストを結合
        full_prompt = " ".join(msg["content"] for msg in result)

        assert sample_message.text in full_prompt
        assert sample_message.user_name in full_prompt
        assert sample_message.channel_id in full_prompt

    def test_build_should_respond_prompt_contains_persona(self, manager, sample_message):
        """ペルソナがプロンプトに含まれること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        assert manager.persona in full_prompt

    def test_build_should_respond_prompt_contains_elapsed_time(self, manager, sample_message):
        """経過時間がプロンプトに含まれること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=300,
            reaction_count=0,
            reply_count=0,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        assert "300" in full_prompt

    def test_build_should_respond_prompt_contains_reaction_count(self, manager, sample_message):
        """リアクション数がプロンプトに含まれること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=5,
            reply_count=0,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        # リアクション数が含まれることを確認
        assert "5" in full_prompt or "リアクション" in full_prompt

    def test_build_should_respond_prompt_contains_reply_count(self, manager, sample_message):
        """返信数がプロンプトに含まれること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=3,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        # 返信数が含まれることを確認
        assert "3" in full_prompt or "返信" in full_prompt

    def test_build_should_respond_prompt_requests_json_format(self, manager, sample_message):
        """JSON形式での回答を要求すること"""
        result = manager.build_should_respond_prompt(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        assert "json" in full_prompt.lower() or "JSON" in full_prompt


class TestBuildResponseGenerationPrompt:
    """応答生成プロンプト構築テスト"""

    @pytest.fixture
    def manager(self):
        """PromptManagerのフィクスチャ"""
        return PromptManager(persona="友達のようなカジュアルな口調で話す")

    @pytest.fixture
    def sample_message(self):
        """テスト用のSlackMessageフィクスチャ"""
        return SlackMessage(
            message_id="1234567890.123456",
            channel_id="C1234567890",
            user_id="U1234567890",
            user_name="testuser",
            text="プログラミングの勉強始めたんだけど、難しいね",
            timestamp=datetime.now(UTC),
            reactions=[],
            reply_count=0,
        )

    @pytest.fixture
    def sample_context(self, sample_message):
        """テスト用のConversationContextフィクスチャ"""
        context = ConversationContext(
            channel_id="C1234567890",
            thread_ts=None,
            messages=[
                SlackMessage(
                    message_id="1234567890.123450",
                    channel_id="C1234567890",
                    user_id="U0000000001",
                    user_name="anotheruser",
                    text="今日も仕事頑張ろう！",
                    timestamp=datetime.now(UTC),
                    reactions=[],
                    reply_count=0,
                ),
            ],
            last_updated=datetime.now(UTC),
        )
        return context

    def test_build_response_generation_prompt_format(self, manager, sample_message):
        """OpenAI形式のメッセージリストが返されること"""
        result = manager.build_response_generation_prompt(
            message=sample_message,
            context=None,
        )

        assert isinstance(result, list)
        assert len(result) >= 1
        for msg in result:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("system", "user", "assistant")

    def test_build_response_generation_prompt_contains_persona(self, manager, sample_message):
        """ペルソナがプロンプトに含まれること"""
        result = manager.build_response_generation_prompt(
            message=sample_message,
            context=None,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        assert manager.persona in full_prompt

    def test_build_response_generation_prompt_contains_message(self, manager, sample_message):
        """対象メッセージがプロンプトに含まれること"""
        result = manager.build_response_generation_prompt(
            message=sample_message,
            context=None,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        assert sample_message.text in full_prompt
        assert sample_message.user_name in full_prompt

    def test_build_response_generation_prompt_with_context(
        self, manager, sample_message, sample_context
    ):
        """コンテキストがプロンプトに含まれること"""
        result = manager.build_response_generation_prompt(
            message=sample_message,
            context=sample_context,
        )

        full_prompt = " ".join(msg["content"] for msg in result)
        # コンテキスト内のメッセージが含まれること
        assert "今日も仕事頑張ろう" in full_prompt or "anotheruser" in full_prompt

    def test_build_response_generation_prompt_without_context(self, manager, sample_message):
        """コンテキストなしでも動作すること"""
        result = manager.build_response_generation_prompt(
            message=sample_message,
            context=None,
        )

        assert isinstance(result, list)
        assert len(result) >= 1
        # メッセージ情報は含まれる
        full_prompt = " ".join(msg["content"] for msg in result)
        assert sample_message.text in full_prompt
