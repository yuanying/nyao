"""リトライ機能

非同期関数のリトライ実行とデコレータを提供します。
"""

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from nyao.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[..., T | Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """非同期関数をリトライ実行

    Args:
        func: 実行する非同期関数
        *args: 関数の位置引数
        max_retries: 最大リトライ回数
        delay: 初回リトライまでの待機時間（秒）
        backoff: リトライごとの待機時間の倍率
        exceptions: リトライ対象の例外タプル
        **kwargs: 関数のキーワード引数

    Returns:
        関数の実行結果

    Raises:
        最後の試行で発生した例外
    """
    last_exception = None

    func_name = getattr(func, "__name__", repr(func))

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await cast(Awaitable[T], func(*args, **kwargs))
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await cast(Awaitable[T], result)
                return cast(T, result)
        except exceptions as e:
            last_exception = e

            if attempt >= max_retries:
                logger.error(
                    "retry_exhausted",
                    function=func_name,
                    max_retries=max_retries,
                    exception=str(e),
                )
                raise

            wait_time = delay * (backoff**attempt)
            logger.warning(
                "retry_attempt",
                function=func_name,
                attempt=attempt + 1,
                max_retries=max_retries,
                wait_time=wait_time,
                exception=str(e),
            )

            await asyncio.sleep(wait_time)

    # ここには到達しないはずだが、型チェッカーのために必要
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry loop exit")


def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """リトライ機能を関数に適用するデコレータ

    Args:
        max_retries: 最大リトライ回数
        delay: 初回リトライまでの待機時間（秒）
        backoff: リトライごとの待機時間の倍率
        exceptions: リトライ対象の例外タプル

    Returns:
        デコレートされた関数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_async(
                func,
                *args,
                max_retries=max_retries,
                delay=delay,
                backoff=backoff,
                exceptions=exceptions,
                **kwargs,
            )

        return wrapper

    return decorator
