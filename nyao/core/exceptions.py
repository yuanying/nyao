"""カスタム例外クラス

Nyaoアプリケーション全体で使用する例外クラスを定義します。
"""

from typing import Any


class NyaoException(Exception):  # noqa: N818
    """Nyaoアプリケーションの基底例外

    すべてのカスタム例外の基底クラスです。
    """

    def to_dict(self) -> dict[str, Any]:
        """ログ出力用の辞書を生成

        Returns:
            例外情報を含む辞書
        """
        return {
            "exception_type": self.__class__.__name__,
            "message": str(self),
        }

    def is_retryable(self) -> bool:
        """リトライ可能かどうか

        Returns:
            リトライ可能な場合True、そうでない場合False
        """
        return False


class SlackAPIError(NyaoException):
    """Slack API関連のエラー

    Slack APIの呼び出しで発生したエラーを表します。
    """

    # リトライ可能なエラーコード
    RETRYABLE_ERROR_CODES = {
        "rate_limited",
        "service_unavailable",
        "internal_error",
    }

    def __init__(self, message: str, error_code: str | None = None):
        """SlackAPIErrorを初期化

        Args:
            message: エラーメッセージ
            error_code: Slack APIのエラーコード
        """
        super().__init__(message)
        self.error_code = error_code

    def to_dict(self) -> dict[str, Any]:
        """ログ出力用の辞書を生成

        Returns:
            エラーコードを含む辞書
        """
        return {
            **super().to_dict(),
            "error_code": self.error_code,
        }

    def is_retryable(self) -> bool:
        """リトライ可能かどうか

        Returns:
            エラーコードがリトライ可能な場合True
        """
        return self.error_code in self.RETRYABLE_ERROR_CODES


class LLMAPIError(NyaoException):
    """LLM API関連のエラー

    LLM APIの呼び出しで発生したエラーを表します。
    """

    # リトライ可能なHTTPステータスコード
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        message: str,
        model: str | None = None,
        status_code: int | None = None,
    ):
        """LLMAPIErrorを初期化

        Args:
            message: エラーメッセージ
            model: 使用したモデル名
            status_code: HTTPステータスコード
        """
        super().__init__(message)
        self.model = model
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        """ログ出力用の辞書を生成

        Returns:
            モデル名とステータスコードを含む辞書
        """
        return {
            **super().to_dict(),
            "model": self.model,
            "status_code": self.status_code,
        }

    def is_retryable(self) -> bool:
        """リトライ可能かどうか

        Returns:
            ステータスコードがリトライ可能な場合True
        """
        return self.status_code in self.RETRYABLE_STATUS_CODES


class ConfigurationError(NyaoException):
    """設定関連のエラー

    設定の読み込みや検証で発生したエラーを表します。
    設定エラーはリトライ不可能です。
    """

    pass


class ContextManagementError(NyaoException):
    """コンテキスト管理関連のエラー

    会話コンテキストの作成、更新、取得で発生したエラーを表します。
    """

    def __init__(self, message: str, retryable: bool = False):
        """ContextManagementErrorを初期化

        Args:
            message: エラーメッセージ
            retryable: リトライ可能かどうか
        """
        super().__init__(message)
        self._retryable = retryable

    def is_retryable(self) -> bool:
        """リトライ可能かどうか

        Returns:
            リトライ可能な場合True
        """
        return self._retryable
