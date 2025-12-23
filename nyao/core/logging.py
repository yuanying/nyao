"""ロギングシステム

構造化ログ（JSON形式）を提供し、本番環境での監視とデバッグを容易にする。
"""

import logging
import os
import sys
from typing import Any

import structlog

# マスキング対象のフィールド名（小文字）
SENSITIVE_FIELDS = {
    "slack_bot_token",
    "slack_app_token",
    "openai_api_key",
    "anthropic_api_key",
    "api_key",
    "token",
    "password",
}

MASK_VALUE = "***MASKED***"


def mask_sensitive_data(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """機密情報を自動的にマスキングするプロセッサー

    Args:
        logger: ロガーインスタンス
        method_name: ログメソッド名
        event_dict: イベント辞書

    Returns:
        マスキング処理後のイベント辞書
    """

    def mask_dict(d: dict[str, Any]) -> dict[str, Any]:
        """辞書内の機密情報を再帰的にマスキング"""
        masked = {}
        for key, value in d.items():
            # キー名を小文字に変換して判定
            if key.lower() in SENSITIVE_FIELDS:
                masked[key] = MASK_VALUE
            elif isinstance(value, dict):
                masked[key] = mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [
                    mask_dict(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                masked[key] = value
        return masked

    return mask_dict(event_dict)


def setup_logging(log_level: str | None = None, development: bool | None = None) -> None:
    """ロギングシステムを初期化

    Args:
        log_level: ログレベル（Noneの場合は設定ファイルから取得）
        development: 開発モード（True: コンソール形式、False: JSON形式、
                     Noneの場合は環境変数 NYAO_ENV から判定）
    """
    # 設定からログレベルを取得
    if log_level is None:
        from nyao.config.settings import get_settings

        settings = get_settings()
        log_level = settings.logging.level

    # 開発環境と本番環境を判定
    if development is None:
        nyao_env = os.getenv("NYAO_ENV", "production")
        development = nyao_env == "development"

    # 共通プロセッサー
    common_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        mask_sensitive_data,
    ]

    # プロセッサーチェーンの選択
    if development:
        processors = common_processors + [structlog.dev.ConsoleRenderer()]
    else:
        processors = common_processors + [structlog.processors.JSONRenderer()]

    # structlog の設定
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 標準ライブラリのloggingも設定
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level),
        stream=sys.stdout,
        force=True,
    )


def get_logger(name: str) -> Any:
    """モジュール別のロガーを取得

    Args:
        name: ロガー名（通常は __name__ を渡す）

    Returns:
        structlog のロガーインスタンス

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("message_received", channel_id="C123456")
    """
    return structlog.get_logger(name)
