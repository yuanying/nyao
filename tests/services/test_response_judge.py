"""応答判定サービスのテスト"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from nyao.config.settings import LiteLLMSettings
from nyao.core.models import ResponseDecision, SlackMessage
from nyao.integrations.llm.judge_agent import ResponseJudgeAgent
from nyao.services.response_judge import ResponseJudgeService


@pytest.fixture
def litellm_settings() -> LiteLLMSettings:
    """テスト用LiteLLMSettings"""
    return LiteLLMSettings(
        model_id="gpt-4o-mini",
        client_args={"api_key": "test-api-key"},
        params={"temperature": 0.5, "max_tokens": 200},
    )


@pytest.fixture
def mock_judge_agent(litellm_settings: LiteLLMSettings) -> ResponseJudgeAgent:
    """モックResponseJudgeAgent"""
    agent = ResponseJudgeAgent(settings=litellm_settings)
    return agent


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


class TestResponseJudgeServiceInit:
    """初期化テスト"""

    def test_init_with_judge_agent(
        self,
        mock_judge_agent: ResponseJudgeAgent,
    ) -> None:
        """ResponseJudgeAgentで初期化できること"""
        service = ResponseJudgeService(judge_agent=mock_judge_agent)
        assert service is not None
        assert service._judge_agent == mock_judge_agent

    def test_init_with_custom_response_delay(
        self,
        mock_judge_agent: ResponseJudgeAgent,
    ) -> None:
        """カスタムresponse_delayで初期化できること"""
        service = ResponseJudgeService(
            judge_agent=mock_judge_agent,
            response_delay=120,
        )
        assert service.response_delay == 120

    def test_init_default_response_delay(
        self,
        mock_judge_agent: ResponseJudgeAgent,
    ) -> None:
        """デフォルトresponse_delayが60秒であること"""
        service = ResponseJudgeService(judge_agent=mock_judge_agent)
        assert service.response_delay == 60


class TestBasicConditions:
    """基本条件チェックテスト"""

    @pytest.fixture
    def service(
        self,
        mock_judge_agent: ResponseJudgeAgent,
    ) -> ResponseJudgeService:
        """テスト用サービス"""
        return ResponseJudgeService(judge_agent=mock_judge_agent)

    async def test_empty_message_returns_no_response(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """空メッセージは応答しない"""
        sample_message.text = ""

        result = await service.should_respond_to_message(
            message=sample_message,
            reactions=[],
            reply_count=0,
        )

        assert result.should_respond is False
        assert "空" in result.reason

    async def test_whitespace_only_message_returns_no_response(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """空白のみメッセージは応答しない"""
        sample_message.text = "   \n\t  "

        result = await service.should_respond_to_message(
            message=sample_message,
            reactions=[],
            reply_count=0,
        )

        assert result.should_respond is False

    async def test_short_message_returns_no_response(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """2文字以下のメッセージは応答しない"""
        sample_message.text = "Hi"

        result = await service.should_respond_to_message(
            message=sample_message,
            reactions=[],
            reply_count=0,
        )

        assert result.should_respond is False
        assert "短" in result.reason

    async def test_minimum_length_message_proceeds(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """3文字のメッセージは基本条件を通過"""
        sample_message.text = "Hey"

        valid_decision = ResponseDecision(
            should_respond=True,
            reason="テスト判定",
            confidence=0.8,
        )

        with patch.object(
            service._judge_agent,
            "judge_should_respond",
            new_callable=AsyncMock,
        ) as mock_judge:
            mock_judge.return_value = valid_decision

            result = await service.should_respond_to_message(
                message=sample_message,
                reactions=[],
                reply_count=0,
            )

            # LLM判定が呼ばれたことを確認
            mock_judge.assert_called_once()
            assert result.should_respond is True

    async def test_basic_condition_rejection_has_high_confidence(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """基本条件拒否時のconfidenceが1.0"""
        sample_message.text = ""

        result = await service.should_respond_to_message(
            message=sample_message,
            reactions=[],
            reply_count=0,
        )

        assert result.confidence == 1.0


class TestLLMJudgment:
    """LLM判定テスト"""

    @pytest.fixture
    def service(
        self,
        mock_judge_agent: ResponseJudgeAgent,
    ) -> ResponseJudgeService:
        """テスト用サービス"""
        return ResponseJudgeService(judge_agent=mock_judge_agent)

    async def test_llm_judge_called_with_correct_params(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """LLMに正しいパラメータが渡されること"""
        valid_decision = ResponseDecision(
            should_respond=True,
            reason="テスト",
            confidence=0.8,
        )

        with patch.object(
            service._judge_agent,
            "judge_should_respond",
            new_callable=AsyncMock,
        ) as mock_judge:
            mock_judge.return_value = valid_decision

            await service.should_respond_to_message(
                message=sample_message,
                reactions=[],
                reply_count=0,
            )

            mock_judge.assert_called_once()
            call_kwargs = mock_judge.call_args.kwargs
            assert call_kwargs["message"] == sample_message
            assert call_kwargs["reaction_count"] == 0
            assert call_kwargs["reply_count"] == 0
            assert "elapsed_seconds" in call_kwargs

    async def test_llm_receives_reaction_count(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """リアクション数がLLMに渡される"""
        valid_decision = ResponseDecision(
            should_respond=True,
            reason="テスト",
            confidence=0.8,
        )

        with patch.object(
            service._judge_agent,
            "judge_should_respond",
            new_callable=AsyncMock,
        ) as mock_judge:
            mock_judge.return_value = valid_decision

            await service.should_respond_to_message(
                message=sample_message,
                reactions=["thumbsup", "heart"],
                reply_count=0,
            )

            call_kwargs = mock_judge.call_args.kwargs
            assert call_kwargs["reaction_count"] == 2

    async def test_llm_receives_reply_count(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """返信数がLLMに渡される"""
        valid_decision = ResponseDecision(
            should_respond=True,
            reason="テスト",
            confidence=0.8,
        )

        with patch.object(
            service._judge_agent,
            "judge_should_respond",
            new_callable=AsyncMock,
        ) as mock_judge:
            mock_judge.return_value = valid_decision

            await service.should_respond_to_message(
                message=sample_message,
                reactions=[],
                reply_count=5,
            )

            call_kwargs = mock_judge.call_args.kwargs
            assert call_kwargs["reply_count"] == 5

    async def test_llm_returns_should_respond_true(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """LLMが応答すべきと判定"""
        valid_decision = ResponseDecision(
            should_respond=True,
            reason="孤独なメッセージに応答",
            confidence=0.85,
        )

        with patch.object(
            service._judge_agent,
            "judge_should_respond",
            new_callable=AsyncMock,
        ) as mock_judge:
            mock_judge.return_value = valid_decision

            result = await service.should_respond_to_message(
                message=sample_message,
                reactions=[],
                reply_count=0,
            )

            assert result.should_respond is True
            assert result.confidence == 0.85

    async def test_llm_returns_should_respond_false(
        self,
        service: ResponseJudgeService,
        sample_message: SlackMessage,
    ) -> None:
        """LLMが応答不要と判定"""
        valid_decision = ResponseDecision(
            should_respond=False,
            reason="応答の必要なし",
            confidence=0.9,
        )

        with patch.object(
            service._judge_agent,
            "judge_should_respond",
            new_callable=AsyncMock,
        ) as mock_judge:
            mock_judge.return_value = valid_decision

            result = await service.should_respond_to_message(
                message=sample_message,
                reactions=[],
                reply_count=0,
            )

            assert result.should_respond is False


class TestElapsedTimeCalculation:
    """経過時間計算テスト"""

    @pytest.fixture
    def service(
        self,
        mock_judge_agent: ResponseJudgeAgent,
    ) -> ResponseJudgeService:
        """テスト用サービス"""
        return ResponseJudgeService(judge_agent=mock_judge_agent)

    def test_elapsed_time_from_recent_message(
        self,
        service: ResponseJudgeService,
    ) -> None:
        """最近のメッセージの経過時間"""
        now = datetime.now(UTC)
        message = SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="テストメッセージ",
            timestamp=now - timedelta(seconds=120),
            reactions=[],
            reply_count=0,
        )

        elapsed = service._calculate_elapsed_time(message)

        # 120秒前後であることを確認（テスト実行時間のマージン込み）
        assert 119 <= elapsed <= 125

    def test_elapsed_time_from_old_message(
        self,
        service: ResponseJudgeService,
    ) -> None:
        """古いメッセージの経過時間"""
        now = datetime.now(UTC)
        message = SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="テストメッセージ",
            timestamp=now - timedelta(hours=2),
            reactions=[],
            reply_count=0,
        )

        elapsed = service._calculate_elapsed_time(message)

        # 7200秒（2時間）前後であることを確認
        assert 7199 <= elapsed <= 7210

    def test_elapsed_time_handles_timezone(
        self,
        service: ResponseJudgeService,
    ) -> None:
        """タイムゾーンが正しく処理される"""
        # UTCで300秒前のメッセージ
        message_time = datetime.now(UTC) - timedelta(seconds=300)
        message = SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="テストメッセージ",
            timestamp=message_time,
            reactions=[],
            reply_count=0,
        )

        elapsed = service._calculate_elapsed_time(message)

        # 300秒前後であることを確認
        assert 299 <= elapsed <= 305
