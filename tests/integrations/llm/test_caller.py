"""LLMCallerのテスト"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from nyao.core.exceptions import LLMAPIError
from nyao.core.models import ConversationContext, LLMResponse, ResponseDecision, SlackMessage
from nyao.integrations.llm.caller import LLMCaller
from nyao.integrations.llm.prompts import PromptManager


class TestLLMCallerInit:
    """LLMCallerの初期化テスト"""

    def test_init_with_agent_and_prompt_manager(self):
        """エージェントとプロンプトマネージャーで初期化できること"""
        mock_agent = MagicMock()
        prompt_manager = PromptManager(persona="テスト用ペルソナ")

        caller = LLMCaller(agent=mock_agent, prompt_manager=prompt_manager)

        assert caller.agent is mock_agent
        assert caller.prompt_manager is prompt_manager

    def test_from_settings_factory(self, tmp_path, monkeypatch):
        """from_settingsファクトリメソッドが動作すること"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
slack:
  channel_ids:
    - C1234567890
litellm:
  model_id: openai/gpt-4o
  client_args:
    api_key: $OPENAI_API_KEY
bot:
  persona: テスト用ペルソナ
""")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        from nyao.config.settings import reload_settings

        settings = reload_settings()

        with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
            caller = LLMCaller.from_settings(settings)

            assert caller.agent is not None
            assert caller.prompt_manager is not None
            assert caller.prompt_manager.persona == "テスト用ペルソナ"


class TestJudgeShouldRespond:
    """応答判定テスト"""

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

    @pytest.fixture
    def mock_caller(self):
        """モック化されたLLMCallerを返すフィクスチャ"""
        mock_agent = MagicMock()
        prompt_manager = PromptManager(persona="テスト用ペルソナ")
        return LLMCaller(agent=mock_agent, prompt_manager=prompt_manager)

    @pytest.mark.asyncio
    async def test_judge_should_respond_returns_response_decision(
        self, mock_caller, sample_message
    ):
        """ResponseDecisionが返されること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content='{"should_respond": true, "reason": "テスト", "confidence": 0.8}',
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        result = await mock_caller.judge_should_respond(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        assert isinstance(result, ResponseDecision)

    @pytest.mark.asyncio
    async def test_judge_should_respond_true(self, mock_caller, sample_message):
        """応答すべき場合にshould_respond=Trueが返されること"""
        json_content = '{"should_respond": true, "reason": "質問あり", "confidence": 0.9}'
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content=json_content,
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        result = await mock_caller.judge_should_respond(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        assert result.should_respond is True
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_judge_should_respond_false(self, mock_caller, sample_message):
        """応答不要な場合にshould_respond=Falseが返されること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content='{"should_respond": false, "reason": "既に返信がある", "confidence": 0.95}',
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        result = await mock_caller.judge_should_respond(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=2,
        )

        assert result.should_respond is False

    @pytest.mark.asyncio
    async def test_judge_should_respond_uses_low_temperature(self, mock_caller, sample_message):
        """temperature=0.3が使用されること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content='{"should_respond": true, "reason": "テスト", "confidence": 0.8}',
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        await mock_caller.judge_should_respond(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        # call_llmが呼ばれた際のtemperature引数を確認
        call_kwargs = mock_caller.agent.call_llm.call_args[1]
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_judge_should_respond_fallback_on_error(self, mock_caller, sample_message):
        """エラー時にshould_respond=Falseが返されること"""
        mock_caller.agent.call_llm = MagicMock(
            side_effect=LLMAPIError("API Error", model="openai/gpt-4o", status_code=500)
        )

        result = await mock_caller.judge_should_respond(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        assert result.should_respond is False
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_judge_should_respond_fallback_on_invalid_json(self, mock_caller, sample_message):
        """不正なJSON時にshould_respond=Falseが返されること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content="これはJSONではありません",
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        result = await mock_caller.judge_should_respond(
            message=sample_message,
            elapsed_seconds=120,
            reaction_count=0,
            reply_count=0,
        )

        assert result.should_respond is False
        assert result.confidence == 0.0


class TestGenerateResponse:
    """応答生成テスト"""

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
    def sample_context(self):
        """テスト用のConversationContextフィクスチャ"""
        return ConversationContext(
            channel_id="C1234567890",
            thread_ts=None,
            messages=[],
            last_updated=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_caller(self):
        """モック化されたLLMCallerを返すフィクスチャ"""
        mock_agent = MagicMock()
        prompt_manager = PromptManager(persona="テスト用ペルソナ")
        return LLMCaller(agent=mock_agent, prompt_manager=prompt_manager)

    @pytest.mark.asyncio
    async def test_generate_response_returns_llm_response(self, mock_caller, sample_message):
        """LLMResponseが返されること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content="頑張ってるね！最初は大変だけど、少しずつ慣れていくよ！",
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        result = await mock_caller.generate_response(message=sample_message)

        assert isinstance(result, LLMResponse)
        assert "頑張ってる" in result.content

    @pytest.mark.asyncio
    async def test_generate_response_uses_high_temperature(self, mock_caller, sample_message):
        """temperature=0.8が使用されること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content="テスト応答",
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        await mock_caller.generate_response(message=sample_message)

        call_kwargs = mock_caller.agent.call_llm.call_args[1]
        assert call_kwargs["temperature"] == 0.8

    @pytest.mark.asyncio
    async def test_generate_response_with_context(
        self, mock_caller, sample_message, sample_context
    ):
        """コンテキスト付きで応答生成できること"""
        mock_caller.agent.call_llm = MagicMock(
            return_value=LLMResponse(
                content="テスト応答",
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )
        )

        result = await mock_caller.generate_response(message=sample_message, context=sample_context)

        assert isinstance(result, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_response_raises_on_error(self, mock_caller, sample_message):
        """エラー時にLLMAPIErrorが送出されること"""
        mock_caller.agent.call_llm = MagicMock(
            side_effect=LLMAPIError("API Error", model="openai/gpt-4o", status_code=500)
        )

        with pytest.raises(LLMAPIError):
            await mock_caller.generate_response(message=sample_message)


class TestParseJsonResponse:
    """JSONパーステスト"""

    @pytest.fixture
    def caller(self):
        """LLMCallerを返すフィクスチャ"""
        mock_agent = MagicMock()
        prompt_manager = PromptManager(persona="テスト用ペルソナ")
        return LLMCaller(agent=mock_agent, prompt_manager=prompt_manager)

    def test_parse_valid_json(self, caller):
        """有効なJSONがパースできること"""
        content = '{"should_respond": true, "reason": "テスト", "confidence": 0.8}'
        result = caller._parse_json_response(content)

        assert result["should_respond"] is True
        assert result["reason"] == "テスト"
        assert result["confidence"] == 0.8

    def test_parse_json_with_markdown_code_block(self, caller):
        """マークダウンコードブロック内のJSONがパースできること"""
        content = """```json
{"should_respond": true, "reason": "テスト", "confidence": 0.8}
```"""
        result = caller._parse_json_response(content)

        assert result["should_respond"] is True

    def test_parse_json_with_markdown_code_block_no_lang(self, caller):
        """言語指定なしのコードブロック内のJSONがパースできること"""
        content = """```
{"should_respond": false, "reason": "テスト", "confidence": 0.5}
```"""
        result = caller._parse_json_response(content)

        assert result["should_respond"] is False

    def test_parse_invalid_json_raises_error(self, caller):
        """不正なJSONでValueErrorが送出されること"""
        content = "これはJSONではありません"

        with pytest.raises(ValueError):
            caller._parse_json_response(content)


class TestLLMCallerRetry:
    """リトライ機能テスト"""

    @pytest.fixture
    def sample_message(self):
        """テスト用のSlackMessageフィクスチャ"""
        return SlackMessage(
            message_id="1234567890.123456",
            channel_id="C1234567890",
            user_id="U1234567890",
            user_name="testuser",
            text="テスト",
            timestamp=datetime.now(UTC),
            reactions=[],
            reply_count=0,
        )

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self, sample_message):
        """リトライ可能なエラーでリトライされること"""
        mock_agent = MagicMock()
        prompt_manager = PromptManager(persona="テスト用ペルソナ")
        caller = LLMCaller(agent=mock_agent, prompt_manager=prompt_manager)

        # 最初の2回は失敗、3回目で成功
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMAPIError("Rate limited", model="openai/gpt-4o", status_code=429)
            return LLMResponse(
                content="成功",
                model="openai/gpt-4o",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="stop",
            )

        mock_agent.call_llm = MagicMock(side_effect=side_effect)

        result = await caller.generate_response(message=sample_message)

        assert result.content == "成功"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self, sample_message):
        """リトライ不可能なエラーでリトライされないこと"""
        mock_agent = MagicMock()
        prompt_manager = PromptManager(persona="テスト用ペルソナ")
        caller = LLMCaller(agent=mock_agent, prompt_manager=prompt_manager)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise LLMAPIError("Unauthorized", model="openai/gpt-4o", status_code=401)

        mock_agent.call_llm = MagicMock(side_effect=side_effect)

        with pytest.raises(LLMAPIError):
            await caller.generate_response(message=sample_message)

        # リトライ不可能なエラーなので1回のみ呼ばれる
        assert call_count == 1
