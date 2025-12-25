"""NyaoAgentのテスト"""

from unittest.mock import MagicMock, patch

import pytest

from nyao.core.exceptions import LLMAPIError
from nyao.core.models import LLMResponse
from nyao.integrations.llm.agent_base import NyaoAgent


class TestNyaoAgentInit:
    """NyaoAgentの初期化テスト"""

    def test_init_with_model_id(self):
        """モデルIDで初期化できること"""
        with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
            agent = NyaoAgent(model_id="openai/gpt-4o")
            assert agent.model_id == "openai/gpt-4o"

    def test_init_with_api_key(self):
        """APIキーを指定して初期化できること"""
        with patch("nyao.integrations.llm.agent_base.LiteLLMModel") as mock_model:
            agent = NyaoAgent(model_id="openai/gpt-4o", api_key="test-api-key")
            assert agent.model_id == "openai/gpt-4o"
            # LiteLLMModelにapi_keyが渡されていることを確認
            mock_model.assert_called()
            call_kwargs = mock_model.call_args[1]
            assert "client_args" in call_kwargs
            assert call_kwargs["client_args"]["api_key"] == "test-api-key"

    def test_init_with_custom_params(self):
        """カスタムパラメータで初期化できること"""
        with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
            default_params = {"temperature": 0.5, "max_tokens": 500}
            agent = NyaoAgent(model_id="openai/gpt-4o", default_params=default_params)
            assert agent.default_params == default_params

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
  params:
    temperature: 0.7
    max_tokens: 1000
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
            agent = NyaoAgent.from_settings(settings)
            assert agent.model_id == "openai/gpt-4o"


class TestNyaoAgentCallLLM:
    """NyaoAgentのLLM呼び出しテスト"""

    @pytest.fixture
    def mock_agent(self):
        """モック化されたNyaoAgentを返すフィクスチャ"""
        with patch("nyao.integrations.llm.agent_base.LiteLLMModel") as mock_model_class:
            # モックのレスポンスを設定
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            agent = NyaoAgent(model_id="openai/gpt-4o")

            # strands.Agentの__call__メソッドをモック
            mock_response = MagicMock()
            mock_response.message = MagicMock()
            mock_response.message.content = [MagicMock(text="テスト応答")]
            mock_response.stop_reason = "end_turn"
            mock_response.metrics = MagicMock()
            mock_response.metrics.inputTokens = 100
            mock_response.metrics.outputTokens = 50

            agent._mock_response = mock_response  # type: ignore[attr-defined]
            yield agent

    def test_call_llm_success(self, mock_agent):
        """LLM呼び出しが成功すること（モック）"""
        messages = [{"role": "user", "content": "こんにちは"}]

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.return_value = mock_agent._mock_response

            result = mock_agent.call_llm(messages)

            assert result is not None
            mock_invoke.assert_called_once()

    def test_call_llm_returns_llm_response(self, mock_agent):
        """LLMResponseが正しく返されること"""
        messages = [{"role": "user", "content": "テスト"}]

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.return_value = mock_agent._mock_response

            result = mock_agent.call_llm(messages)

            assert isinstance(result, LLMResponse)
            assert result.content == "テスト応答"
            assert result.model == "openai/gpt-4o"
            assert "prompt_tokens" in result.usage
            assert "completion_tokens" in result.usage

    def test_call_llm_with_custom_temperature(self, mock_agent):
        """カスタムtemperatureが使用されること"""
        messages = [{"role": "user", "content": "テスト"}]

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.return_value = mock_agent._mock_response

            mock_agent.call_llm(messages, temperature=0.3)

            # 呼び出し時にtemperatureが渡されていることを確認
            mock_invoke.assert_called_once()

    def test_call_llm_with_custom_max_tokens(self, mock_agent):
        """カスタムmax_tokensが使用されること"""
        messages = [{"role": "user", "content": "テスト"}]

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.return_value = mock_agent._mock_response

            mock_agent.call_llm(messages, max_tokens=200)

            mock_invoke.assert_called_once()


class TestNyaoAgentErrorHandling:
    """NyaoAgentのエラーハンドリングテスト"""

    @pytest.fixture
    def mock_agent(self):
        """モック化されたNyaoAgentを返すフィクスチャ"""
        with patch("nyao.integrations.llm.agent_base.LiteLLMModel"):
            agent = NyaoAgent(model_id="openai/gpt-4o")
            yield agent

    def test_call_llm_raises_llm_api_error_on_failure(self, mock_agent):
        """API失敗時にLLMAPIErrorが送出されること"""
        messages = [{"role": "user", "content": "テスト"}]

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.side_effect = Exception("API Error")

            with pytest.raises(LLMAPIError):
                mock_agent.call_llm(messages)

    def test_call_llm_includes_model_in_error(self, mock_agent):
        """エラーにモデル名が含まれること"""
        messages = [{"role": "user", "content": "テスト"}]

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.side_effect = Exception("API Error")

            with pytest.raises(LLMAPIError) as exc_info:
                mock_agent.call_llm(messages)

            assert exc_info.value.model == "openai/gpt-4o"

    def test_call_llm_includes_status_code_in_error(self, mock_agent):
        """エラーにステータスコードが含まれること（可能な場合）"""
        messages = [{"role": "user", "content": "テスト"}]

        class MockAPIError(Exception):
            status_code = 429

        with patch.object(mock_agent, "_invoke_agent") as mock_invoke:
            mock_invoke.side_effect = MockAPIError("Rate limited")

            with pytest.raises(LLMAPIError) as exc_info:
                mock_agent.call_llm(messages)

            assert exc_info.value.status_code == 429
