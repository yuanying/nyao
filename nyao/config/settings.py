"""設定管理システム

環境変数やYAMLファイルから設定を読み込み、アプリケーション全体で一貫した設定管理を提供する。
"""

import os
import random
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResponseDelaySettings(BaseModel):
    """応答遅延設定"""

    base: int = Field(default=60, ge=0, description="基本待機時間（秒）")
    jitter: int = Field(default=10, ge=0, description="ランダムな揺らぎ（秒）")


class SlackSettings(BaseModel):
    """Slack設定"""

    channel_ids: list[str] = Field(description="監視対象チャンネルIDのリスト")

    @field_validator("channel_ids")
    @classmethod
    def validate_channel_ids(cls, v: list[str]) -> list[str]:
        """チャンネルIDのフォーマットを検証"""
        for channel_id in v:
            if not re.match(r"^C[A-Z0-9]+$", channel_id):
                raise ValueError(f"Invalid channel ID format: {channel_id}")
        return v


class BotSettings(BaseModel):
    """Bot動作設定"""

    response_delay: ResponseDelaySettings = Field(
        default_factory=ResponseDelaySettings, description="応答判定までの待機時間設定"
    )
    persona: str = Field(
        default="友達のようなカジュアルな口調で話す", description="ボットのペルソナ設定"
    )


class LoggingSettings(BaseModel):
    """ログ設定"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="ログレベル"
    )


class LiteLLMSettings(BaseModel):
    """LiteLLM設定（strands-agents LiteLLMModel形式）"""

    model_id: str = Field(description="LiteLLMモデルID（プロバイダー/モデル形式）")
    client_args: dict[str, Any] = Field(default_factory=dict, description="LiteLLMクライアント引数")
    params: dict[str, Any] = Field(default_factory=dict, description="LiteLLMモデルパラメータ")


class Settings(BaseSettings):
    """アプリケーション設定

    環境変数とYAMLファイルから設定を読み込む。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 環境変数から読み込む必須項目
    slack_bot_token: str = Field(description="Slack Bot User OAuth Token")
    slack_app_token: str = Field(description="Slack App-Level Token")
    config: str = Field(default="config.yaml", description="設定ファイルのパス")

    # YAMLファイルから読み込む設定
    slack: SlackSettings
    litellm: LiteLLMSettings
    bot: BotSettings = Field(default_factory=BotSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def __init__(self, **kwargs):
        """設定の初期化

        YAMLファイルから設定を読み込み、環境変数を展開する。
        """
        # YAMLファイルから設定を読み込む
        config_path = kwargs.get("config") or os.getenv("NYAO_CONFIG", "config.yaml")
        yaml_config = self._load_yaml_config(config_path)

        # 環境変数を展開
        yaml_config = self._expand_env_vars(yaml_config)

        # YAMLの設定をkwargsにマージ
        kwargs.update(yaml_config)

        super().__init__(**kwargs)

    @staticmethod
    def _load_yaml_config(config_path: str) -> dict[str, Any]:
        """YAMLファイルから設定を読み込む"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path) as f:
            config = yaml.safe_load(f)

        return config or {}

    @staticmethod
    def _expand_env_vars(config: dict[str, Any]) -> dict[str, Any]:
        """設定値内の環境変数参照（$VAR_NAME形式）を展開する"""

        def expand_value(value: Any) -> Any:
            if isinstance(value, str) and value.startswith("$"):
                env_var_name = value[1:]
                env_value = os.getenv(env_var_name)
                if env_value is None:
                    raise ValueError(f"Environment variable not found: {env_var_name}")
                return env_value
            elif isinstance(value, dict):
                return {k: expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_value(item) for item in value]
            return value

        return expand_value(config)


# シングルトンインスタンス
_settings: Settings | None = None


def get_settings() -> Settings:
    """設定のシングルトンインスタンスを取得"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """設定を再読み込み（開発時のみ使用）"""
    global _settings
    _settings = None
    return get_settings()


def get_response_delay_with_jitter() -> int:
    """jitterを適用した待機時間を取得

    Returns:
        待機時間（秒）: base ± random(0, jitter)
    """
    settings = get_settings()
    base = settings.bot.response_delay.base
    jitter = settings.bot.response_delay.jitter

    # base - jitter から base + jitter の範囲でランダムな値を返す
    return base + random.randint(-jitter, jitter)
