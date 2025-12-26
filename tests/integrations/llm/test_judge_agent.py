"""応答判定エージェントのテスト

ResponseJudgeAgentクラスのテストを行います。
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from nyao.config.settings import LiteLLMSettings
from nyao.core.exceptions import LLMAPIError
from nyao.core.models import ResponseDecision, SlackMessage
from nyao.integrations.llm.judge_agent import ResponseJudgeAgent


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


class TestResponseJudgeAgentInit:
    """ResponseJudgeAgent初期化のテスト"""

    def test_init_with_settings(self, litellm_settings: LiteLLMSettings) -> None:
        """LiteLLMSettingsで初期化できること"""
        agent = ResponseJudgeAgent(settings=litellm_settings)

        assert agent is not None
        assert agent._settings == litellm_settings

    def test_init_with_custom_persona(self, litellm_settings: LiteLLMSettings) -> None:
        """カスタムペルソナで初期化できること"""
        custom_persona = "テスト用ペルソナ"
        agent = ResponseJudgeAgent(settings=litellm_settings, persona=custom_persona)

        assert agent._prompt_manager.persona == custom_persona


class TestJudgeShouldRespond:
    """judge_should_respondのテスト"""

    @pytest.fixture
    def agent(self, litellm_settings: LiteLLMSettings) -> ResponseJudgeAgent:
        """テスト用ResponseJudgeAgent"""
        return ResponseJudgeAgent(settings=litellm_settings)

    @pytest.fixture
    def valid_decision(self) -> ResponseDecision:
        """有効なResponseDecision"""
        return ResponseDecision(
            should_respond=True,
            reason="誰からも反応がないため、応答する必要がある",
            confidence=0.85,
        )

    async def test_judge_returns_response_decision(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
        valid_decision: ResponseDecision,
    ) -> None:
        """判定結果がResponseDecisionで返されること"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.return_value = valid_decision

            result = await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            assert isinstance(result, ResponseDecision)
            assert result.should_respond is True
            assert result.reason == "誰からも反応がないため、応答する必要がある"
            assert result.confidence == 0.85

    async def test_judge_with_should_not_respond(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
    ) -> None:
        """応答不要と判定されること"""
        decision = ResponseDecision(
            should_respond=False,
            reason="既にリアクションがあるため",
            confidence=0.9,
        )

        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.return_value = decision

            result = await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=60,
                reaction_count=3,
                reply_count=1,
            )

            assert result.should_respond is False

    async def test_judge_uses_correct_temperature(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
        valid_decision: ResponseDecision,
    ) -> None:
        """temperature=0.3でLLMを呼び出すこと"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.return_value = valid_decision

            await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            mock_structured_output.assert_called_once()
            _, kwargs = mock_structured_output.call_args
            assert kwargs.get("temperature") == 0.3

    async def test_judge_uses_correct_max_tokens(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
        valid_decision: ResponseDecision,
    ) -> None:
        """max_tokens=200でLLMを呼び出すこと"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.return_value = valid_decision

            await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            mock_structured_output.assert_called_once()
            _, kwargs = mock_structured_output.call_args
            assert kwargs.get("max_tokens") == 200

    async def test_judge_passes_response_decision_model(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
        valid_decision: ResponseDecision,
    ) -> None:
        """ResponseDecisionモデルがstructured_outputに渡されること"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.return_value = valid_decision

            await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            mock_structured_output.assert_called_once()
            _, kwargs = mock_structured_output.call_args
            assert kwargs.get("output_model") == ResponseDecision


class TestFallbackBehavior:
    """フォールバック動作のテスト"""

    @pytest.fixture
    def agent(self, litellm_settings: LiteLLMSettings) -> ResponseJudgeAgent:
        """テスト用ResponseJudgeAgent"""
        return ResponseJudgeAgent(settings=litellm_settings)

    async def test_fallback_on_llm_error(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
    ) -> None:
        """LLMエラー時にデフォルトで「応答しない」を返すこと"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.side_effect = LLMAPIError(
                message="API Error",
                model="gpt-4o-mini",
                status_code=500,
            )

            result = await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            assert result.should_respond is False
            assert "エラー" in result.reason

    async def test_fallback_on_unexpected_error(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
    ) -> None:
        """予期しないエラー時にデフォルトで「応答しない」を返すこと"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.side_effect = ValueError("Unexpected error")

            result = await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            assert result.should_respond is False
            assert "エラー" in result.reason

    async def test_fallback_confidence_is_zero(
        self,
        agent: ResponseJudgeAgent,
        sample_message: SlackMessage,
    ) -> None:
        """フォールバック時のconfidenceが0.0であること"""
        with patch.object(
            agent._agent, "structured_output", new_callable=AsyncMock
        ) as mock_structured_output:
            mock_structured_output.side_effect = LLMAPIError(
                message="API Error",
                model="gpt-4o-mini",
                status_code=500,
            )

            result = await agent.judge_should_respond(
                message=sample_message,
                elapsed_seconds=300,
                reaction_count=0,
                reply_count=0,
            )

            assert result.confidence == 0.0
