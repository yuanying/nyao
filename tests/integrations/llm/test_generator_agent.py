"""応答生成エージェントのテスト

ResponseGeneratorAgentクラスのテストを行います。
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from nyao.config.settings import LiteLLMSettings
from nyao.core.exceptions import LLMAPIError
from nyao.core.models import ConversationContext, LLMResponse, SlackMessage
from nyao.integrations.llm.generator_agent import ResponseGeneratorAgent


@pytest.fixture
def litellm_settings() -> LiteLLMSettings:
    """テスト用LiteLLMSettings"""
    return LiteLLMSettings(
        model_id="gpt-4o-mini",
        client_args={"api_key": "test-api-key"},
        params={"temperature": 0.5, "max_tokens": 200},
    )


@pytest.fixture
def sample_message() -> SlackMessage:
    """テスト用SlackMessage"""
    return SlackMessage(
        message_id="msg-001",
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="今日は良い天気ですね！",
        timestamp=datetime.now(UTC),
        reactions=[],
        reply_count=0,
    )


@pytest.fixture
def sample_thread_context(sample_message: SlackMessage) -> ConversationContext:
    """テスト用スレッドコンテキスト"""
    return ConversationContext(
        channel_id="C12345678",
        thread_ts="1234567890.123456",
        messages=[sample_message],
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def sample_channel_context() -> ConversationContext:
    """テスト用チャンネルコンテキスト"""
    channel_message = SlackMessage(
        message_id="msg-channel-001",
        channel_id="C12345678",
        user_id="U11111111",
        user_name="bob",
        text="チャンネルでの会話です",
        timestamp=datetime.now(UTC),
    )
    return ConversationContext(
        channel_id="C12345678",
        thread_ts=None,
        messages=[channel_message],
        last_updated=datetime.now(UTC),
    )


class TestResponseGeneratorAgentInit:
    """ResponseGeneratorAgent初期化のテスト"""

    def test_init_with_settings(self, litellm_settings: LiteLLMSettings) -> None:
        """LiteLLMSettingsで初期化できること"""
        agent = ResponseGeneratorAgent(settings=litellm_settings)

        assert agent is not None
        assert agent._settings == litellm_settings

    def test_init_with_custom_persona(self, litellm_settings: LiteLLMSettings) -> None:
        """カスタムペルソナで初期化できること"""
        custom_persona = "テスト用ペルソナ"
        agent = ResponseGeneratorAgent(settings=litellm_settings, persona=custom_persona)

        assert agent._prompt_manager.persona == custom_persona


class TestGenerateResponse:
    """generate_responseのテスト"""

    @pytest.fixture
    def agent(self, litellm_settings: LiteLLMSettings) -> ResponseGeneratorAgent:
        """テスト用ResponseGeneratorAgent"""
        return ResponseGeneratorAgent(settings=litellm_settings)

    @pytest.fixture
    def valid_llm_response(self) -> LLMResponse:
        """有効なLLMResponse"""
        return LLMResponse(
            content="いい天気ですね！お出かけ日和ですよ。",
            model="gpt-4o-mini",
            usage={},
            finish_reason="stop",
        )

    async def test_generate_returns_llm_response(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        valid_llm_response: LLMResponse,
    ) -> None:
        """生成結果がLLMResponseで返されること"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            result = await agent.generate_response(message=sample_message)

            assert isinstance(result, LLMResponse)
            assert result.content == "いい天気ですね！お出かけ日和ですよ。"

    async def test_generate_with_thread_context(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        sample_thread_context: ConversationContext,
        valid_llm_response: LLMResponse,
    ) -> None:
        """スレッドコンテキスト付きで生成できること"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            result = await agent.generate_response(
                message=sample_message, thread_context=sample_thread_context
            )

            assert isinstance(result, LLMResponse)
            mock_call_llm.assert_called_once()

    async def test_generate_with_channel_context(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        sample_channel_context: ConversationContext,
        valid_llm_response: LLMResponse,
    ) -> None:
        """チャンネルコンテキスト付きで生成できること"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            result = await agent.generate_response(
                message=sample_message, channel_context=sample_channel_context
            )

            assert isinstance(result, LLMResponse)
            mock_call_llm.assert_called_once()

    async def test_generate_with_both_contexts(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        sample_thread_context: ConversationContext,
        sample_channel_context: ConversationContext,
        valid_llm_response: LLMResponse,
    ) -> None:
        """両コンテキスト付きで生成できること"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            result = await agent.generate_response(
                message=sample_message,
                thread_context=sample_thread_context,
                channel_context=sample_channel_context,
            )

            assert isinstance(result, LLMResponse)
            mock_call_llm.assert_called_once()

    async def test_generate_without_context(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        valid_llm_response: LLMResponse,
    ) -> None:
        """コンテキストなしで生成できること"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            result = await agent.generate_response(message=sample_message)

            assert isinstance(result, LLMResponse)
            mock_call_llm.assert_called_once()

    async def test_generate_uses_correct_temperature(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        valid_llm_response: LLMResponse,
    ) -> None:
        """temperature=0.8でLLMを呼び出すこと"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            await agent.generate_response(message=sample_message)

            mock_call_llm.assert_called_once()
            _, kwargs = mock_call_llm.call_args
            assert kwargs.get("temperature") == 0.8

    async def test_generate_uses_correct_max_tokens(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
        valid_llm_response: LLMResponse,
    ) -> None:
        """max_tokens=300でLLMを呼び出すこと"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.return_value = valid_llm_response

            await agent.generate_response(message=sample_message)

            mock_call_llm.assert_called_once()
            _, kwargs = mock_call_llm.call_args
            assert kwargs.get("max_tokens") == 300


class TestErrorHandling:
    """エラーハンドリングのテスト"""

    @pytest.fixture
    def agent(self, litellm_settings: LiteLLMSettings) -> ResponseGeneratorAgent:
        """テスト用ResponseGeneratorAgent"""
        return ResponseGeneratorAgent(settings=litellm_settings)

    async def test_llm_error_is_raised(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
    ) -> None:
        """LLMAPIErrorがそのままスローされること"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.side_effect = LLMAPIError(
                message="API Error",
                model="gpt-4o-mini",
                status_code=500,
            )

            with pytest.raises(LLMAPIError) as exc_info:
                await agent.generate_response(message=sample_message)

            assert exc_info.value.status_code == 500

    async def test_no_fallback_on_error(
        self,
        agent: ResponseGeneratorAgent,
        sample_message: SlackMessage,
    ) -> None:
        """エラー時にフォールバック応答を返さないこと（例外がスローされること）"""
        with patch.object(agent._agent, "call_llm", new_callable=AsyncMock) as mock_call_llm:
            mock_call_llm.side_effect = LLMAPIError(
                message="API Error",
                model="gpt-4o-mini",
                status_code=429,
            )

            # フォールバック応答ではなく、例外がスローされることを確認
            with pytest.raises(LLMAPIError):
                await agent.generate_response(message=sample_message)
