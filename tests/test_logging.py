"""ロギングシステムのテストコード"""

import json

import pytest

from nyao.core.logging import get_logger, setup_logging


class TestLoggingSetup:
    """ロギングシステムのセットアップに関するテスト"""

    def test_setup_logging_with_default_level(self, tmp_path, monkeypatch, capsys):
        """デフォルトレベルでロギングシステムがセットアップできること"""
        # 環境変数と設定ファイルを準備
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        # 設定を再読み込み
        from nyao.config.settings import reload_settings

        reload_settings()

        # ロギングシステムをセットアップ（デフォルトレベル）
        setup_logging()

        logger = get_logger("test")
        logger.info("test_message")

        # ログが出力されることを確認
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_setup_logging_with_custom_level(self, tmp_path, monkeypatch, capsys):
        """カスタムログレベルでセットアップできること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        # DEBUGレベルでセットアップ
        setup_logging(log_level="DEBUG")

        logger = get_logger("test")
        logger.debug("debug_message")

        # DEBUGログが出力されることを確認
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_setup_logging_in_development_mode(self, tmp_path, monkeypatch, capsys):
        """開発モードでセットアップできること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        # 開発モードでセットアップ
        setup_logging(development=True)

        logger = get_logger("test")
        logger.info("test_message")

        # ログが出力されることを確認
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_setup_logging_in_production_mode(self, tmp_path, monkeypatch, capsys):
        """本番モードでセットアップできること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        # 本番モードでセットアップ
        setup_logging(development=False)

        logger = get_logger("test")
        logger.info("test_message")

        # ログが出力されることを確認
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_setup_logging_detects_env_from_nyao_env(self, tmp_path, monkeypatch, capsys):
        """NYAO_ENV環境変数から環境を判定できること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")
        monkeypatch.setenv("NYAO_ENV", "development")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        # development引数なしでセットアップ（NYAO_ENVから判定）
        setup_logging()

        logger = get_logger("test")
        logger.info("test_message")

        # ログが出力されることを確認
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestLogFormatting:
    """ログフォーマットに関するテスト"""

    def test_json_format_in_production_mode(self, tmp_path, monkeypatch, capsys):
        """本番モードでJSON形式でログが出力されること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", channel_id="C123456", user_id="U789012")

        # ログ出力を取得
        captured = capsys.readouterr()
        output = captured.out.strip()

        # JSON形式でパースできることを確認
        log_entry = json.loads(output)

        # 必須フィールドの確認
        assert log_entry["event"] == "test_event"
        assert log_entry["level"] == "info"
        assert log_entry["channel_id"] == "C123456"
        assert log_entry["user_id"] == "U789012"
        assert "timestamp" in log_entry
        assert log_entry["logger"] == "test"

    def test_console_format_in_development_mode(self, tmp_path, monkeypatch, capsys):
        """開発モードでコンソール形式でログが出力されること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=True)
        logger = get_logger("test")

        logger.info("test_event", channel_id="C123456")

        # ログ出力を取得
        captured = capsys.readouterr()
        output = captured.out

        # コンソール形式（JSON以外）であることを確認
        # JSON形式ではパースできないことを確認
        with pytest.raises(json.JSONDecodeError):
            json.loads(output.strip())

        # イベント名が含まれていることを確認
        assert "test_event" in output

    def test_timestamp_format_is_iso8601(self, tmp_path, monkeypatch, capsys):
        """タイムスタンプがISO8601形式であること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event")

        captured = capsys.readouterr()
        output = captured.out.strip()
        log_entry = json.loads(output)

        # タイムスタンプがISO8601形式であることを確認
        timestamp = log_entry["timestamp"]
        from datetime import datetime

        # ISO8601形式でパースできることを確認
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_log_contains_logger_name(self, tmp_path, monkeypatch, capsys):
        """ログにロガー名が含まれること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("my.module.name")

        logger.info("test_event")

        captured = capsys.readouterr()
        output = captured.out.strip()
        log_entry = json.loads(output)

        # ロガー名が含まれること
        assert log_entry["logger"] == "my.module.name"

    def test_log_contains_log_level(self, tmp_path, monkeypatch, capsys):
        """ログにログレベルが含まれること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.warning("test_warning")

        captured = capsys.readouterr()
        output = captured.out.strip()
        log_entry = json.loads(output)

        # ログレベルが含まれること
        assert log_entry["level"] == "warning"


class TestSensitiveDataMasking:
    """機密情報マスキングに関するテスト"""

    def test_mask_slack_bot_token(self, tmp_path, monkeypatch, capsys):
        """slack_bot_tokenが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", slack_bot_token="xoxb-123456789-abcdefgh")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["slack_bot_token"] == "***MASKED***"
        assert "xoxb-" not in output

    def test_mask_slack_app_token(self, tmp_path, monkeypatch, capsys):
        """slack_app_tokenが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", slack_app_token="xapp-123456789-abcdefgh")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["slack_app_token"] == "***MASKED***"
        assert "xapp-" not in output

    def test_mask_openai_api_key(self, tmp_path, monkeypatch, capsys):
        """openai_api_keyが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", openai_api_key="sk-proj-1234567890abcdefgh")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["openai_api_key"] == "***MASKED***"
        assert "sk-proj-" not in output

    def test_mask_anthropic_api_key(self, tmp_path, monkeypatch, capsys):
        """anthropic_api_keyが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", anthropic_api_key="sk-ant-1234567890abcdefgh")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["anthropic_api_key"] == "***MASKED***"
        assert "sk-ant-" not in output

    def test_mask_generic_api_key(self, tmp_path, monkeypatch, capsys):
        """api_keyが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", api_key="secret_key_12345")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["api_key"] == "***MASKED***"
        assert "secret_key_12345" not in output

    def test_mask_generic_token(self, tmp_path, monkeypatch, capsys):
        """tokenが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", token="my_secret_token")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["token"] == "***MASKED***"
        assert "my_secret_token" not in output

    def test_mask_password(self, tmp_path, monkeypatch, capsys):
        """passwordが自動的にマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", password="my_password123")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["password"] == "***MASKED***"
        assert "my_password123" not in output

    def test_mask_case_insensitive(self, tmp_path, monkeypatch, capsys):
        """大文字小文字を区別せずにマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", API_KEY="secret1", Api_Key="secret2", api_key="secret3")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        assert log_entry["API_KEY"] == "***MASKED***"
        assert log_entry["Api_Key"] == "***MASKED***"
        assert log_entry["api_key"] == "***MASKED***"

    def test_mask_nested_dict(self, tmp_path, monkeypatch, capsys):
        """ネストされた辞書内の機密情報がマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info(
            "test_event",
            config={
                "slack": {"slack_bot_token": "xoxb-secret"},
                "llm": {"api_key": "sk-secret"},
            },
        )

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        # ネストされた辞書内でもマスキングされる
        assert log_entry["config"]["slack"]["slack_bot_token"] == "***MASKED***"
        assert log_entry["config"]["llm"]["api_key"] == "***MASKED***"

    def test_mask_list_of_dicts(self, tmp_path, monkeypatch, capsys):
        """辞書のリスト内の機密情報がマスキングされること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info(
            "test_event",
            credentials=[
                {"name": "slack", "token": "xoxb-secret1"},
                {"name": "openai", "api_key": "sk-secret2"},
            ],
        )

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        # リスト内の辞書でもマスキングされる
        assert log_entry["credentials"][0]["token"] == "***MASKED***"
        assert log_entry["credentials"][1]["api_key"] == "***MASKED***"

    def test_non_sensitive_data_not_masked(self, tmp_path, monkeypatch, capsys):
        """機密情報でないデータはマスキングしないこと"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        logger.info("test_event", channel_id="C123456", user_id="U789012", message="Hello")

        captured = capsys.readouterr()
        output = captured.out
        log_entry = json.loads(output.strip())

        # 機密情報でないデータはマスキングされない
        assert log_entry["channel_id"] == "C123456"
        assert log_entry["user_id"] == "U789012"
        assert log_entry["message"] == "Hello"


class TestLogLevelFiltering:
    """ログレベルフィルタリングに関するテスト"""

    def test_debug_level_shows_all_logs(self, tmp_path, monkeypatch, capsys):
        """DEBUGレベルですべてのログが表示されること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(log_level="DEBUG", development=False)
        logger = get_logger("test")

        logger.debug("debug_msg")
        logger.info("info_msg")
        logger.warning("warning_msg")

        captured = capsys.readouterr()
        output = captured.out

        # すべてのログレベルが出力されること
        assert "debug_msg" in output
        assert "info_msg" in output
        assert "warning_msg" in output

    def test_info_level_filters_debug(self, tmp_path, monkeypatch, capsys):
        """INFOレベルでDEBUGが非表示になること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(log_level="INFO", development=False)
        logger = get_logger("test")

        logger.debug("debug_msg")
        logger.info("info_msg")
        logger.warning("warning_msg")

        captured = capsys.readouterr()
        output = captured.out

        # DEBUGは出力されず、INFO以上が出力されること
        assert "debug_msg" not in output
        assert "info_msg" in output
        assert "warning_msg" in output

    def test_warning_level_filters_info_and_debug(self, tmp_path, monkeypatch, capsys):
        """WARNINGレベルでINFO以下が非表示になること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(log_level="WARNING", development=False)
        logger = get_logger("test")

        logger.debug("debug_msg")
        logger.info("info_msg")
        logger.warning("warning_msg")
        logger.error("error_msg")

        captured = capsys.readouterr()
        output = captured.out

        # WARNING以上のみが出力されること
        assert "debug_msg" not in output
        assert "info_msg" not in output
        assert "warning_msg" in output
        assert "error_msg" in output

    def test_error_level_filters_warning_and_below(self, tmp_path, monkeypatch, capsys):
        """ERRORレベルでWARNING以下が非表示になること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(log_level="ERROR", development=False)
        logger = get_logger("test")

        logger.info("info_msg")
        logger.warning("warning_msg")
        logger.error("error_msg")
        logger.critical("critical_msg")

        captured = capsys.readouterr()
        output = captured.out

        # ERROR以上のみが出力されること
        assert "info_msg" not in output
        assert "warning_msg" not in output
        assert "error_msg" in output
        assert "critical_msg" in output

    def test_critical_level_filters_error_and_below(self, tmp_path, monkeypatch, capsys):
        """CRITICALレベルでERROR以下が非表示になること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(log_level="CRITICAL", development=False)
        logger = get_logger("test")

        logger.warning("warning_msg")
        logger.error("error_msg")
        logger.critical("critical_msg")

        captured = capsys.readouterr()
        output = captured.out

        # CRITICALのみが出力されること
        assert "warning_msg" not in output
        assert "error_msg" not in output
        assert "critical_msg" in output


class TestContextInformation:
    """コンテキスト情報に関するテスト"""

    def test_bind_context_information(self, tmp_path, monkeypatch, capsys):
        """コンテキスト情報がバインドできること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        # コンテキスト情報をバインド
        logger = logger.bind(request_id="req-12345", user_id="U789012")
        logger.info("test_event")

        captured = capsys.readouterr()
        output = captured.out.strip()
        log_entry = json.loads(output)

        # バインドした情報が含まれていること
        assert log_entry["request_id"] == "req-12345"
        assert log_entry["user_id"] == "U789012"

    def test_context_persists_across_logs(self, tmp_path, monkeypatch, capsys):
        """コンテキスト情報が複数ログで保持されること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        # コンテキスト情報をバインド
        logger = logger.bind(request_id="req-12345")

        logger.info("event1")
        logger.info("event2")

        captured = capsys.readouterr()
        output_lines = captured.out.strip().split("\n")

        # 両方のログにコンテキスト情報が含まれていること
        log1 = json.loads(output_lines[0])
        log2 = json.loads(output_lines[1])

        assert log1["request_id"] == "req-12345"
        assert log2["request_id"] == "req-12345"

    def test_unbind_context_information(self, tmp_path, monkeypatch, capsys):
        """コンテキスト情報がアンバインドできること"""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

        import yaml

        config_file = tmp_path / "config.yaml"
        config_data = {
            "slack": {"channel_ids": ["C123456"]},
            "litellm": {"model": "openai/gpt-4o"},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        monkeypatch.setenv("NYAO_CONFIG", str(config_file))

        from nyao.config.settings import reload_settings

        reload_settings()

        setup_logging(development=False)
        logger = get_logger("test")

        # コンテキスト情報をバインド
        logger = logger.bind(request_id="req-12345")
        logger.info("event1")

        # アンバインド
        logger = logger.unbind("request_id")
        logger.info("event2")

        captured = capsys.readouterr()
        output_lines = captured.out.strip().split("\n")

        # 最初のログにはコンテキスト情報があり、2つ目にはないこと
        log1 = json.loads(output_lines[0])
        log2 = json.loads(output_lines[1])

        assert log1["request_id"] == "req-12345"
        assert "request_id" not in log2
