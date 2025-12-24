"""カスタム例外クラスのテストコード"""

from nyao.core.exceptions import (
    ConfigurationError,
    ContextManagementError,
    LLMAPIError,
    NyaoException,
    SlackAPIError,
)


class TestNyaoException:
    """NyaoException基底例外のテスト"""

    def test_nyao_exception_basic(self):
        """NyaoExceptionが作成できること"""
        exc = NyaoException()
        assert isinstance(exc, Exception)
        assert isinstance(exc, NyaoException)

    def test_nyao_exception_with_message(self):
        """メッセージ付きでNyaoExceptionを作成できること"""
        exc = NyaoException("Test error message")
        assert str(exc) == "Test error message"

    def test_nyao_exception_to_dict(self):
        """to_dict()で辞書化できること"""
        exc = NyaoException("Test error")
        result = exc.to_dict()

        assert isinstance(result, dict)
        assert result["exception_type"] == "NyaoException"
        assert result["message"] == "Test error"

    def test_nyao_exception_is_not_retryable(self):
        """基底例外はデフォルトでリトライ不可であること"""
        exc = NyaoException("Test error")
        assert exc.is_retryable() is False


class TestSlackAPIError:
    """SlackAPIErrorのテスト"""

    def test_slack_api_error_with_error_code(self):
        """SlackAPIErrorにerror_code属性があること"""
        exc = SlackAPIError("Slack API error", error_code="rate_limited")

        assert str(exc) == "Slack API error"
        assert exc.error_code == "rate_limited"

    def test_slack_api_error_without_error_code(self):
        """error_codeなしでSlackAPIErrorを作成できること"""
        exc = SlackAPIError("Slack API error")

        assert str(exc) == "Slack API error"
        assert exc.error_code is None

    def test_slack_api_error_retryable(self):
        """リトライ可能なエラーコードを判定できること"""
        # リトライ可能なエラーコード
        retryable_codes = ["rate_limited", "service_unavailable", "internal_error"]
        for code in retryable_codes:
            exc = SlackAPIError("Test error", error_code=code)
            assert exc.is_retryable() is True, f"{code} should be retryable"

        # リトライ不可能なエラーコード
        non_retryable_codes = ["invalid_auth", "channel_not_found", "not_in_channel"]
        for code in non_retryable_codes:
            exc = SlackAPIError("Test error", error_code=code)
            assert exc.is_retryable() is False, f"{code} should not be retryable"

    def test_slack_api_error_to_dict(self):
        """to_dict()でerror_codeが含まれること"""
        exc = SlackAPIError("Test error", error_code="rate_limited")
        result = exc.to_dict()

        assert result["exception_type"] == "SlackAPIError"
        assert result["message"] == "Test error"
        assert result["error_code"] == "rate_limited"


class TestLLMAPIError:
    """LLMAPIErrorのテスト"""

    def test_llm_api_error_with_model_and_status(self):
        """LLMAPIErrorにmodel/status_code属性があること"""
        exc = LLMAPIError("LLM API error", model="openai/gpt-4o", status_code=429)

        assert str(exc) == "LLM API error"
        assert exc.model == "openai/gpt-4o"
        assert exc.status_code == 429

    def test_llm_api_error_without_optional_params(self):
        """オプショナルパラメータなしでLLMAPIErrorを作成できること"""
        exc = LLMAPIError("LLM API error")

        assert str(exc) == "LLM API error"
        assert exc.model is None
        assert exc.status_code is None

    def test_llm_api_error_retryable_status_codes(self):
        """リトライ可能なステータスコードを判定できること"""
        # リトライ可能なステータスコード
        retryable_codes = [429, 500, 502, 503, 504]
        for code in retryable_codes:
            exc = LLMAPIError("Test error", status_code=code)
            assert exc.is_retryable() is True, f"{code} should be retryable"

        # リトライ不可能なステータスコード
        non_retryable_codes = [400, 401, 403, 404]
        for code in non_retryable_codes:
            exc = LLMAPIError("Test error", status_code=code)
            assert exc.is_retryable() is False, f"{code} should not be retryable"

    def test_llm_api_error_to_dict(self):
        """to_dict()でmodel/status_codeが含まれること"""
        exc = LLMAPIError("Test error", model="openai/gpt-4o", status_code=429)
        result = exc.to_dict()

        assert result["exception_type"] == "LLMAPIError"
        assert result["message"] == "Test error"
        assert result["model"] == "openai/gpt-4o"
        assert result["status_code"] == 429


class TestConfigurationError:
    """ConfigurationErrorのテスト"""

    def test_configuration_error_not_retryable(self):
        """ConfigurationErrorがリトライ不可であること"""
        exc = ConfigurationError("Invalid configuration")

        assert str(exc) == "Invalid configuration"
        assert exc.is_retryable() is False


class TestContextManagementError:
    """ContextManagementErrorのテスト"""

    def test_context_management_error(self):
        """ContextManagementErrorが作成できること"""
        exc = ContextManagementError("Context error")

        assert str(exc) == "Context error"

    def test_context_management_error_retryable(self):
        """retryableパラメータでリトライ可能性を制御できること"""
        # リトライ可能
        exc_retryable = ContextManagementError("Context error", retryable=True)
        assert exc_retryable.is_retryable() is True

        # リトライ不可能（デフォルト）
        exc_not_retryable = ContextManagementError("Context error")
        assert exc_not_retryable.is_retryable() is False


class TestExceptionInheritance:
    """例外の継承関係のテスト"""

    def test_exception_inheritance(self):
        """すべての例外がNyaoExceptionを継承していること"""
        exceptions = [
            SlackAPIError("test"),
            LLMAPIError("test"),
            ConfigurationError("test"),
            ContextManagementError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, NyaoException)
            assert isinstance(exc, Exception)


class TestExceptionStringRepresentation:
    """例外の文字列表現のテスト"""

    def test_exception_str_representation(self):
        """例外の文字列表現が適切であること"""
        exc1 = NyaoException("Base error")
        assert str(exc1) == "Base error"

        exc2 = SlackAPIError("Slack error", error_code="rate_limited")
        assert str(exc2) == "Slack error"

        exc3 = LLMAPIError("LLM error", model="gpt-4o", status_code=429)
        assert str(exc3) == "LLM error"


class TestExceptionWithCause:
    """例外の原因保持のテスト"""

    def test_exception_with_cause(self):
        """原因となる例外を保持できること"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise NyaoException("Wrapped error") from e
        except NyaoException as exc:
            assert str(exc) == "Wrapped error"
            assert isinstance(exc.__cause__, ValueError)
            assert str(exc.__cause__) == "Original error"
