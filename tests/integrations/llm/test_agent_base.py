"""NyaoAgentのテストコード"""

from unittest.mock import MagicMock, patch

import pytest

from nyao.config.settings import LiteLLMSettings
from nyao.core.exceptions import LLMAPIError
from nyao.core.models import LLMResponse
from nyao.integrations.llm.agent_base import NyaoAgent


class _MockAPIError(Exception):
    """テスト用のAPIエラーモック（status_code属性付き）"""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@pytest.fixture
def litellm_settings() -> LiteLLMSettings:
    """テスト用のLiteLLMSettings"""
    return LiteLLMSettings(
        model_id="openai/gpt-4o",
        client_args={"api_key": "test-api-key"},
        params={"temperature": 0.7, "max_tokens": 1000},
    )


class TestNyaoAgentInit:
    """NyaoAgentの初期化テスト"""

    def test_init_with_settings(self, litellm_settings: LiteLLMSettings):
        """LiteLLMSettingsで初期化できること"""
        with patch("nyao.integrations.llm.agent_base.Agent"):
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                agent = NyaoAgent(settings=litellm_settings)

                assert agent._settings == litellm_settings
                assert agent._system_prompt is None

    def test_init_with_system_prompt(self, litellm_settings: LiteLLMSettings):
        """system_prompt付きで初期化できること"""
        system_prompt = "あなたは友達のように話すアシスタントです。"

        with patch("nyao.integrations.llm.agent_base.Agent"):
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                agent = NyaoAgent(settings=litellm_settings, system_prompt=system_prompt)

                assert agent._system_prompt == system_prompt

    def test_init_creates_litellm_model(self, litellm_settings: LiteLLMSettings):
        """LiteLLMModelが正しく作成されること"""
        with patch("nyao.integrations.llm.agent_base.Agent"):
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel") as mock_model:
                NyaoAgent(settings=litellm_settings)

                mock_model.assert_called_once_with(
                    model_id=litellm_settings.model_id,
                    client_args=litellm_settings.client_args,
                    params=litellm_settings.params,
                )

    def test_init_creates_agent_with_model(self, litellm_settings: LiteLLMSettings):
        """strands.Agentがモデルとともに作成されること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel") as mock_model:
                mock_model_instance = MagicMock()
                mock_model.return_value = mock_model_instance

                NyaoAgent(settings=litellm_settings, system_prompt="test prompt")

                mock_agent.assert_called_once_with(
                    model=mock_model_instance,
                    system_prompt="test prompt",
                )


class TestNyaoAgentCallLLM:
    """call_llmメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_call_llm_returns_llm_response(self, litellm_settings: LiteLLMSettings):
        """LLMResponseが返されること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                # Agentの__call__の戻り値をモック
                mock_agent_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.message = {"content": [{"text": "こんにちは！"}]}
                mock_result.stop_reason = "end_turn"
                mock_agent_instance.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)
                response = await agent.call_llm("テストプロンプト")

                assert isinstance(response, LLMResponse)
                assert response.content == "こんにちは！"

    @pytest.mark.asyncio
    async def test_call_llm_passes_prompt_to_agent(self, litellm_settings: LiteLLMSettings):
        """promptがstrands.Agentに渡されること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.message = {"content": [{"text": "response"}]}
                mock_result.stop_reason = "end_turn"
                mock_agent_instance.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)
                await agent.call_llm("テストプロンプト")

                # Agentが正しいプロンプトで呼び出されたか確認
                mock_agent_instance.assert_called_with("テストプロンプト")

    @pytest.mark.asyncio
    async def test_call_llm_with_custom_temperature(self, litellm_settings: LiteLLMSettings):
        """カスタムtemperatureが使用されること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel") as mock_model_class:
                mock_agent_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.message = {"content": [{"text": "response"}]}
                mock_result.stop_reason = "end_turn"
                mock_agent_instance.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                mock_model_instance = MagicMock()
                mock_model_class.return_value = mock_model_instance

                agent = NyaoAgent(settings=litellm_settings)
                await agent.call_llm("テストプロンプト", temperature=0.3)

                # update_configが正しいtemperatureで呼ばれたか確認
                mock_model_instance.update_config.assert_called_once_with(temperature=0.3)

    @pytest.mark.asyncio
    async def test_call_llm_with_custom_max_tokens(self, litellm_settings: LiteLLMSettings):
        """カスタムmax_tokensが使用されること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel") as mock_model_class:
                mock_agent_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.message = {"content": [{"text": "response"}]}
                mock_result.stop_reason = "end_turn"
                mock_agent_instance.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                mock_model_instance = MagicMock()
                mock_model_class.return_value = mock_model_instance

                agent = NyaoAgent(settings=litellm_settings)
                await agent.call_llm("テストプロンプト", max_tokens=200)

                # update_configが正しいmax_tokensで呼ばれたか確認
                mock_model_instance.update_config.assert_called_once_with(max_tokens=200)


class TestNyaoAgentRetry:
    """リトライ機能のテスト"""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(self, litellm_settings: LiteLLMSettings):
        """429エラーでリトライされること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()

                # 最初の2回は429エラー、3回目で成功
                rate_limit_error = _MockAPIError("Rate limit exceeded", 429)

                mock_result = MagicMock()
                mock_result.message = {"content": [{"text": "success"}]}
                mock_result.stop_reason = "end_turn"

                mock_agent_instance.side_effect = [
                    rate_limit_error,
                    rate_limit_error,
                    mock_result,
                ]
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)
                response = await agent.call_llm("テストプロンプト")

                assert response.content == "success"
                assert mock_agent_instance.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, litellm_settings: LiteLLMSettings):
        """500系エラーでリトライされること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()

                server_error = _MockAPIError("Internal server error", 500)

                mock_result = MagicMock()
                mock_result.message = {"content": [{"text": "success"}]}
                mock_result.stop_reason = "end_turn"

                mock_agent_instance.side_effect = [server_error, mock_result]
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)
                response = await agent.call_llm("テストプロンプト")

                assert response.content == "success"

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, litellm_settings: LiteLLMSettings):
        """最大3回リトライ後にLLMAPIErrorがスローされること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()

                rate_limit_error = _MockAPIError("Rate limit exceeded", 429)

                mock_agent_instance.side_effect = rate_limit_error
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)

                with pytest.raises(LLMAPIError):
                    await agent.call_llm("テストプロンプト")

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, litellm_settings: LiteLLMSettings):
        """400系エラーではリトライしないこと"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()

                auth_error = _MockAPIError("Unauthorized", 401)

                mock_agent_instance.side_effect = auth_error
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)

                with pytest.raises(LLMAPIError):
                    await agent.call_llm("テストプロンプト")

                # リトライされずに1回のみ呼び出される
                assert mock_agent_instance.call_count == 1


class TestNyaoAgentErrorHandling:
    """エラーハンドリングのテスト"""

    @pytest.mark.asyncio
    async def test_llm_api_error_contains_model_info(self, litellm_settings: LiteLLMSettings):
        """LLMAPIErrorにモデル情報が含まれること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()

                error = _MockAPIError("API Error", 401)

                mock_agent_instance.side_effect = error
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)

                with pytest.raises(LLMAPIError) as exc_info:
                    await agent.call_llm("テストプロンプト")

                assert exc_info.value.model == litellm_settings.model_id

    @pytest.mark.asyncio
    async def test_llm_api_error_contains_status_code(self, litellm_settings: LiteLLMSettings):
        """LLMAPIErrorにステータスコードが含まれること"""
        with patch("nyao.integrations.llm.agent_base.Agent") as mock_agent_class:
            with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
                mock_agent_instance = MagicMock()

                error = _MockAPIError("API Error", 500)

                mock_agent_instance.side_effect = error
                mock_agent_class.return_value = mock_agent_instance

                agent = NyaoAgent(settings=litellm_settings)

                with pytest.raises(LLMAPIError) as exc_info:
                    await agent.call_llm("テストプロンプト")

                assert exc_info.value.status_code == 500
