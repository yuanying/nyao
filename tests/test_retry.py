"""リトライ機能のテストコード"""

from unittest.mock import AsyncMock

import pytest

from nyao.utils.retry import retry_async, with_retry


class CustomError(Exception):
    """テスト用のカスタムエラー"""

    pass


class AnotherError(Exception):
    """テスト用の別のエラー"""

    pass


class TestRetryAsyncBasic:
    """retry_async関数の基本機能のテスト"""

    @pytest.mark.asyncio
    async def test_retry_async_success_on_first_attempt(self):
        """初回で成功する関数がリトライされないこと"""
        mock_func = AsyncMock(return_value="success")

        result = await retry_async(mock_func, max_retries=3)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_success_after_retries(self):
        """リトライ後に成功すること"""
        mock_func = AsyncMock(
            side_effect=[CustomError("Error 1"), CustomError("Error 2"), "success"]
        )

        result = await retry_async(mock_func, max_retries=3, delay=0.01, exceptions=(CustomError,))

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_exhausts_retries(self):
        """最大リトライ回数を超えたら例外が送出されること"""
        mock_func = AsyncMock(side_effect=CustomError("Persistent error"))

        with pytest.raises(CustomError, match="Persistent error"):
            await retry_async(mock_func, max_retries=2, delay=0.01, exceptions=(CustomError,))

        # max_retries=2の場合、初回 + 2回のリトライ = 3回呼び出し
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_with_different_exception(self):
        """指定外の例外は即座に送出されること"""
        mock_func = AsyncMock(side_effect=AnotherError("Different error"))

        with pytest.raises(AnotherError, match="Different error"):
            await retry_async(mock_func, max_retries=3, delay=0.01, exceptions=(CustomError,))

        # リトライされずに即座に例外が送出されるので、1回のみ呼び出し
        assert mock_func.call_count == 1


class TestRetryAsyncBackoff:
    """retry_asyncのバックオフ検証のテスト"""

    @pytest.mark.asyncio
    async def test_retry_async_backoff_timing(self, mock_asyncio_sleep):
        """指数バックオフが正しく動作すること"""
        mock_func = AsyncMock(
            side_effect=[CustomError("Error 1"), CustomError("Error 2"), "success"]
        )

        result = await retry_async(
            mock_func, max_retries=3, delay=0.1, backoff=2.0, exceptions=(CustomError,)
        )

        assert result == "success"
        # sleepが正しい遅延時間で呼ばれたことを確認
        # 1回目のリトライ: 0.1秒, 2回目のリトライ: 0.2秒
        sleep_delays = mock_asyncio_sleep.get_sleep_delays()
        assert 0.1 in sleep_delays  # 1回目のリトライ
        assert 0.2 in sleep_delays  # 2回目のリトライ

    @pytest.mark.asyncio
    async def test_retry_async_custom_delay(self, mock_asyncio_sleep):
        """カスタム遅延時間が使用されること"""
        mock_func = AsyncMock(side_effect=[CustomError("Error"), "success"])

        result = await retry_async(mock_func, max_retries=3, delay=0.05, exceptions=(CustomError,))

        assert result == "success"
        # 0.05秒でsleepが呼ばれたことを確認
        mock_asyncio_sleep.assert_any_call(0.05)

    @pytest.mark.asyncio
    async def test_retry_async_custom_backoff(self, mock_asyncio_sleep):
        """カスタムバックオフ倍率が使用されること"""
        mock_func = AsyncMock(
            side_effect=[
                CustomError("Error 1"),
                CustomError("Error 2"),
                CustomError("Error 3"),
                "success",
            ]
        )

        result = await retry_async(
            mock_func, max_retries=4, delay=0.05, backoff=3.0, exceptions=(CustomError,)
        )

        assert result == "success"
        # sleepが正しい遅延時間で呼ばれたことを確認
        # 1回目: 0.05秒, 2回目: 0.15秒, 3回目: 0.45秒
        sleep_delays = mock_asyncio_sleep.get_sleep_delays()
        assert any(pytest.approx(0.05) == d for d in sleep_delays)
        assert any(pytest.approx(0.15) == d for d in sleep_delays)
        assert any(pytest.approx(0.45) == d for d in sleep_delays)


class TestWithRetryDecorator:
    """with_retryデコレータのテスト"""

    @pytest.mark.asyncio
    async def test_with_retry_decorator_basic(self):
        """デコレータが基本的に機能すること"""
        call_count = 0

        @with_retry(max_retries=3, delay=0.01, exceptions=(CustomError,))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise CustomError("Retry me")
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_decorator_with_params(self):
        """デコレータにパラメータを渡せること"""

        @with_retry(max_retries=2, delay=0.01, backoff=2.0, exceptions=(CustomError,))
        async def test_func():
            raise CustomError("Always fails")

        with pytest.raises(CustomError):
            await test_func()

    @pytest.mark.asyncio
    async def test_with_retry_decorator_preserves_function_metadata(self):
        """関数のメタデータが保持されること"""

        @with_retry(max_retries=3, delay=0.01)
        async def test_func():
            """Test function docstring"""
            return "success"

        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring"


class TestRetryAsyncMultipleExceptions:
    """retry_asyncの複数例外対応のテスト"""

    @pytest.mark.asyncio
    async def test_retry_async_multiple_exceptions(self):
        """複数の例外タイプを指定できること"""
        mock_func = AsyncMock(
            side_effect=[CustomError("Error 1"), AnotherError("Error 2"), "success"]
        )

        result = await retry_async(
            mock_func,
            max_retries=3,
            delay=0.01,
            exceptions=(CustomError, AnotherError),
        )

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_exception_hierarchy(self):
        """例外階層が正しく処理されること"""

        class ParentError(Exception):
            pass

        class ChildError(ParentError):
            pass

        mock_func = AsyncMock(side_effect=[ChildError("Child error"), "success"])

        # 親クラスを指定した場合、子クラスの例外もキャッチされる
        result = await retry_async(mock_func, max_retries=3, delay=0.01, exceptions=(ParentError,))

        assert result == "success"
        assert mock_func.call_count == 2


class TestRetryAsyncWithAsyncFunction:
    """retry_asyncの非同期関数対応のテスト"""

    @pytest.mark.asyncio
    async def test_retry_async_with_async_function(self):
        """非同期関数が正しくリトライされること"""
        call_count = 0

        async def async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise CustomError("Retry me")
            return "async success"

        result = await retry_async(async_func, max_retries=3, delay=0.01, exceptions=(CustomError,))

        assert result == "async success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_with_args_and_kwargs(self):
        """引数・キーワード引数が正しく渡されること"""
        call_count = 0

        async def async_func(arg1, arg2, kwarg1=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise CustomError("Retry me")
            return f"{arg1}-{arg2}-{kwarg1}"

        result = await retry_async(
            async_func,
            "value1",
            "value2",
            max_retries=3,
            delay=0.01,
            exceptions=(CustomError,),
            kwarg1="kwvalue",
        )

        assert result == "value1-value2-kwvalue"
        assert call_count == 2


class TestRetryAsyncEdgeCases:
    """retry_asyncのエッジケースのテスト"""

    @pytest.mark.asyncio
    async def test_retry_async_max_retries_zero(self):
        """max_retries=0でリトライされないこと"""
        mock_func = AsyncMock(side_effect=CustomError("Error"))

        with pytest.raises(CustomError):
            await retry_async(mock_func, max_retries=0, delay=0.01, exceptions=(CustomError,))

        # max_retries=0の場合、初回のみ呼び出し
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_with_no_exception(self):
        """例外が発生しない場合、即座に結果を返すこと"""
        mock_func = AsyncMock(return_value="immediate success")

        result = await retry_async(mock_func, max_retries=3, delay=0.01)

        assert result == "immediate success"
        assert mock_func.call_count == 1
