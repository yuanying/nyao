"""設定管理システムのテストコード"""

import pytest
import yaml
from pydantic import ValidationError

from nyao.config.settings import (
    BotSettings,
    LiteLLMSettings,
    LoggingSettings,
    get_response_delay_with_jitter,
    get_settings,
    reload_settings,
)


class TestSettings:
    """設定管理のテスト"""

    def test_env_vars_loaded_correctly(self, tmp_path, monkeypatch):
        """環境変数が正しく読み込まれること"""
        # 環境変数を設定
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")

        # 最小限の設定ファイルを作成
        config_file = tmp_path / "config.yaml"
        config_data = {
            "litellm": {"model_id": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        # 設定を再読み込み
        reload_settings()
        settings = get_settings()

        assert settings.slack_bot_token == "xoxb-test-token"
        assert settings.slack_app_token == "xapp-test-token"

    def test_yaml_config_loaded_correctly(self, tmp_path, monkeypatch):
        """YAMLファイルから設定が正しく読み込まれること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")

        config_file = tmp_path / "config.yaml"
        config_data = {
            "litellm": {
                "model_id": "openai/gpt-4o",
                "params": {"temperature": 0.8, "max_tokens": 2000},
            },
            "bot": {"response_delay": {"base": 90, "jitter": 20}, "persona": "テストペルソナ"},
            "logging": {"level": "DEBUG"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        reload_settings()
        settings = get_settings()

        assert settings.litellm.model_id == "openai/gpt-4o"
        assert settings.litellm.params["temperature"] == 0.8
        assert settings.litellm.params["max_tokens"] == 2000
        assert settings.bot.response_delay.base == 90
        assert settings.bot.response_delay.jitter == 20
        assert settings.bot.persona == "テストペルソナ"
        assert settings.logging.level == "DEBUG"

    def test_env_var_expansion_in_config(self, tmp_path, monkeypatch):
        """設定値内の環境変数参照が正しく展開されること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        config_file = tmp_path / "config.yaml"
        config_data = {
            "litellm": {
                "model_id": "openai/gpt-4o",
                "client_args": {"api_key": "$OPENAI_API_KEY"},
            },
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        reload_settings()
        settings = get_settings()

        assert settings.litellm.client_args["api_key"] == "sk-test-key"

    def test_default_values_applied(self, tmp_path, monkeypatch):
        """デフォルト値が正しく適用されること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")

        # 最小限の設定ファイル（デフォルト値を使用）
        config_file = tmp_path / "config.yaml"
        config_data = {
            "litellm": {"model_id": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        reload_settings()
        settings = get_settings()

        # デフォルト値の確認
        assert settings.bot.response_delay.base == 60
        assert settings.bot.response_delay.jitter == 10
        assert settings.bot.persona == "友達のようなカジュアルな口調で話す"
        assert settings.logging.level == "INFO"

    def test_missing_required_fields_raises_error(self, tmp_path, monkeypatch):
        """必須項目が欠けている場合にエラーが発生すること"""
        # SLACK_BOT_TOKENが欠けている
        # .envファイルからの読み込みを防ぐため作業ディレクトリを変更
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")

        config_file = tmp_path / "config.yaml"
        config_data = {
            "litellm": {"model_id": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        with pytest.raises(ValidationError):
            reload_settings()

    def test_jitter_applied_correctly(self, tmp_path, monkeypatch):
        """jitterを適用した待機時間が正しい範囲内にあること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")

        config_file = tmp_path / "config.yaml"
        config_data = {
            "litellm": {"model_id": "openai/gpt-4o"},
            "bot": {"response_delay": {"base": 60, "jitter": 10}},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        reload_settings()

        # 複数回実行して範囲内にあることを確認
        for _ in range(10):
            delay = get_response_delay_with_jitter()
            assert 50 <= delay <= 70  # base(60) - jitter(10) から base(60) + jitter(10)


class TestBotSettings:
    """Bot動作設定のテスト"""

    def test_default_values(self):
        """デフォルト値が正しく設定されること"""
        settings = BotSettings()
        assert settings.response_delay.base == 60
        assert settings.response_delay.jitter == 10
        assert settings.persona == "友達のようなカジュアルな口調で話す"

    def test_custom_values(self):
        """カスタム値が正しく設定されること"""
        settings = BotSettings(response_delay={"base": 90, "jitter": 20}, persona="テストペルソナ")  # type: ignore[arg-type]
        assert settings.response_delay.base == 90
        assert settings.response_delay.jitter == 20
        assert settings.persona == "テストペルソナ"


class TestLoggingSettings:
    """ログ設定のテスト"""

    def test_default_level(self):
        """デフォルトのログレベルがINFOであること"""
        settings = LoggingSettings()
        assert settings.level == "INFO"

    def test_custom_level(self):
        """カスタムログレベルが設定できること"""
        settings = LoggingSettings(level="DEBUG")
        assert settings.level == "DEBUG"

    def test_invalid_level_raises_error(self):
        """不正なログレベルが拒否されること"""
        with pytest.raises(ValidationError):
            LoggingSettings(level="INVALID")  # type: ignore[arg-type]


class TestLiteLLMSettings:
    """LiteLLM設定のテスト"""

    def test_model_id_required(self):
        """model_idが必須であること"""
        with pytest.raises(ValidationError):
            LiteLLMSettings()  # type: ignore[call-arg]

    def test_minimal_config(self):
        """最小限の設定（model_idのみ）で動作すること"""
        settings = LiteLLMSettings(model_id="openai/gpt-4o")
        assert settings.model_id == "openai/gpt-4o"
        assert settings.client_args == {}
        assert settings.params == {}

    def test_full_config(self):
        """すべてのフィールドが設定できること"""
        settings = LiteLLMSettings(
            model_id="openai/gpt-4o",
            client_args={"api_key": "sk-test", "api_base": "https://api.example.com"},
            params={"temperature": 0.7, "max_tokens": 1000},
        )
        assert settings.model_id == "openai/gpt-4o"
        assert settings.client_args["api_key"] == "sk-test"
        assert settings.client_args["api_base"] == "https://api.example.com"
        assert settings.params["temperature"] == 0.7
        assert settings.params["max_tokens"] == 1000
