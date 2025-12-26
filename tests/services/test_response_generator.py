"""応答生成サービスのテスト"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from nyao.config.settings import LiteLLMSettings
from nyao.core.exceptions import LLMAPIError
from nyao.core.models import ConversationContext, LLMResponse, SlackMessage
from nyao.integrations.llm.generator_agent import ResponseGeneratorAgent
from nyao.services.response_generator import ResponseGeneratorService


@pytest.fixture
def litellm_settings() -> LiteLLMSettings:
    """テスト用LiteLLMSettings"""
    return LiteLLMSettings(
        model_id="gpt-4o-mini",
        client_args={"api_key": "test-api-key"},
        params={"temperature": 0.8, "max_tokens": 300},
    )


@pytest.fixture
def mock_generator_agent(litellm_settings: LiteLLMSettings) -> ResponseGeneratorAgent:
    """モックResponseGeneratorAgent"""
    return ResponseGeneratorAgent(settings=litellm_settings)


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
def sample_thread_context() -> ConversationContext:
    """テスト用スレッドコンテキスト"""
    now = datetime.now(UTC)
    return ConversationContext(
        channel_id="C12345678",
        thread_ts="1234567890.123456",
        messages=[
            SlackMessage(
                message_id="msg-thread-001",
                channel_id="C12345678",
                thread_ts="1234567890.123456",
                user_id="U11111111",
                user_name="alice",
                text="スレッドの最初のメッセージ",
                timestamp=now - timedelta(minutes=10),
            ),
            SlackMessage(
                message_id="msg-thread-002",
                channel_id="C12345678",
                thread_ts="1234567890.123456",
                user_id="U22222222",
                user_name="bob",
                text="スレッドへの返信",
                timestamp=now - timedelta(minutes=5),
            ),
        ],
        last_updated=now - timedelta(minutes=5),
    )


@pytest.fixture
def sample_channel_context() -> ConversationContext:
    """テスト用チャンネルコンテキスト"""
    now = datetime.now(UTC)
    return ConversationContext(
        channel_id="C12345678",
        thread_ts=None,
        messages=[
            SlackMessage(
                message_id="msg-channel-001",
                channel_id="C12345678",
                user_id="U33333333",
                user_name="charlie",
                text="チャンネルでの会話1",
                timestamp=now - timedelta(minutes=30),
            ),
            SlackMessage(
                message_id="msg-channel-002",
                channel_id="C12345678",
                user_id="U44444444",
                user_name="david",
                text="チャンネルでの会話2",
                timestamp=now - timedelta(minutes=20),
            ),
        ],
        last_updated=now - timedelta(minutes=20),
    )


class TestResponseGeneratorServiceInit:
    """初期化テスト"""

    def test_init_with_generator_agent(
        self,
        mock_generator_agent: ResponseGeneratorAgent,
    ) -> None:
        """ResponseGeneratorAgentで初期化できること"""
        service = ResponseGeneratorService(generator_agent=mock_generator_agent)
        assert service is not None

    def test_init_stores_generator_agent(
        self,
        mock_generator_agent: ResponseGeneratorAgent,
    ) -> None:
        """エージェントが正しく格納されること"""
        service = ResponseGeneratorService(generator_agent=mock_generator_agent)
        assert service._generator_agent == mock_generator_agent


class TestPostProcessResponse:
    """後処理テスト"""

    @pytest.fixture
    def service(
        self,
        mock_generator_agent: ResponseGeneratorAgent,
    ) -> ResponseGeneratorService:
        """テスト用サービス"""
        return ResponseGeneratorService(generator_agent=mock_generator_agent)

    def test_post_process_strips_whitespace(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """前後の空白が削除されること"""
        result = service._post_process_response("  こんにちは！  \n")
        assert result == "こんにちは！"

    def test_post_process_removes_double_quotes(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """ダブルクォートが削除されること"""
        result = service._post_process_response('"こんにちは！"')
        assert result == "こんにちは！"

    def test_post_process_removes_single_quotes(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """シングルクォートが削除されること"""
        result = service._post_process_response("'こんにちは！'")
        assert result == "こんにちは！"

    def test_post_process_removes_japanese_quotes(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """日本語カギ括弧が削除されること"""
        result = service._post_process_response("「こんにちは！」")
        assert result == "こんにちは！"

    def test_post_process_does_not_remove_partial_quotes(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """片側だけの引用符は削除しない"""
        result = service._post_process_response('"こんにちは！')
        assert result == '"こんにちは！'

        result = service._post_process_response('こんにちは！"')
        assert result == 'こんにちは！"'

    def test_post_process_handles_empty_string(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """空文字列を正しく処理"""
        result = service._post_process_response("")
        assert result == ""

    def test_post_process_strips_then_removes_quotes(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """空白削除後に引用符削除が行われること"""
        result = service._post_process_response('  "こんにちは！"  ')
        assert result == "こんにちは！"


class TestFallbackResponse:
    """フォールバック応答テスト"""

    @pytest.fixture
    def service(
        self,
        mock_generator_agent: ResponseGeneratorAgent,
    ) -> ResponseGeneratorService:
        """テスト用サービス"""
        return ResponseGeneratorService(generator_agent=mock_generator_agent)

    def test_get_fallback_response_returns_string(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """文字列を返すこと"""
        result = service._get_fallback_response()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_fallback_response_returns_from_list(
        self,
        service: ResponseGeneratorService,
    ) -> None:
        """リスト内の応答を返すこと"""
        result = service._get_fallback_response()
        assert result in ResponseGeneratorService.FALLBACK_RESPONSES

    async def test_generate_response_returns_fallback_on_llm_error(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
    ) -> None:
        """LLMエラー時にフォールバックを返す"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.side_effect = LLMAPIError("API呼び出しエラー")

            result = await service.generate_response(
                message=sample_message,
            )

            assert result in ResponseGeneratorService.FALLBACK_RESPONSES

    async def test_generate_response_returns_fallback_on_unexpected_error(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
    ) -> None:
        """予期しないエラー時にフォールバックを返す"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.side_effect = RuntimeError("予期しないエラー")

            result = await service.generate_response(
                message=sample_message,
            )

            assert result in ResponseGeneratorService.FALLBACK_RESPONSES


class TestGenerateResponse:
    """応答生成テスト"""

    @pytest.fixture
    def service(
        self,
        mock_generator_agent: ResponseGeneratorAgent,
    ) -> ResponseGeneratorService:
        """テスト用サービス"""
        return ResponseGeneratorService(generator_agent=mock_generator_agent)

    @pytest.fixture
    def mock_llm_response(self) -> LLMResponse:
        """モックLLMレスポンス"""
        return LLMResponse(
            content="いい天気だね！散歩したくなるよね。",
            model="gpt-4o-mini",
            usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
            finish_reason="stop",
        )

    async def test_generate_response_success(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
        mock_llm_response: LLMResponse,
    ) -> None:
        """応答が正しく生成されること"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_llm_response

            result = await service.generate_response(
                message=sample_message,
            )

            assert result == mock_llm_response.content

    async def test_generate_response_with_thread_context_only(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
        sample_thread_context: ConversationContext,
        mock_llm_response: LLMResponse,
    ) -> None:
        """スレッドコンテキストのみで生成できること"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_llm_response

            result = await service.generate_response(
                message=sample_message,
                thread_context=sample_thread_context,
            )

            assert result == mock_llm_response.content
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs["thread_context"] == sample_thread_context
            assert call_kwargs["channel_context"] is None

    async def test_generate_response_with_channel_context_only(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
        sample_channel_context: ConversationContext,
        mock_llm_response: LLMResponse,
    ) -> None:
        """チャンネルコンテキストのみで生成できること"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_llm_response

            result = await service.generate_response(
                message=sample_message,
                channel_context=sample_channel_context,
            )

            assert result == mock_llm_response.content
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs["thread_context"] is None
            assert call_kwargs["channel_context"] == sample_channel_context

    async def test_generate_response_with_both_contexts(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
        sample_thread_context: ConversationContext,
        sample_channel_context: ConversationContext,
        mock_llm_response: LLMResponse,
    ) -> None:
        """両コンテキストで生成できること"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_llm_response

            result = await service.generate_response(
                message=sample_message,
                thread_context=sample_thread_context,
                channel_context=sample_channel_context,
            )

            assert result == mock_llm_response.content
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs["thread_context"] == sample_thread_context
            assert call_kwargs["channel_context"] == sample_channel_context

    async def test_generate_response_without_any_context(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
        mock_llm_response: LLMResponse,
    ) -> None:
        """コンテキストなしでも生成できること"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_llm_response

            result = await service.generate_response(
                message=sample_message,
            )

            assert result == mock_llm_response.content
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs["thread_context"] is None
            assert call_kwargs["channel_context"] is None

    async def test_generator_agent_called_with_correct_params(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
        mock_llm_response: LLMResponse,
    ) -> None:
        """エージェントに正しいパラメータが渡されること"""
        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_llm_response

            await service.generate_response(
                message=sample_message,
            )

            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs["message"] == sample_message
            assert "thread_context" in call_kwargs
            assert "channel_context" in call_kwargs

    async def test_generate_response_applies_post_processing(
        self,
        service: ResponseGeneratorService,
        sample_message: SlackMessage,
    ) -> None:
        """後処理が適用されること"""
        llm_response = LLMResponse(
            content='  "後処理テスト"  ',
            model="gpt-4o-mini",
            usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
            finish_reason="stop",
        )

        with patch.object(
            service._generator_agent,
            "generate_response",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = llm_response

            result = await service.generate_response(
                message=sample_message,
            )

            # 空白とダブルクォートが削除されていること
            assert result == "後処理テスト"
