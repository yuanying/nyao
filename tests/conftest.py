"""テスト共通フィクスチャ"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest

# 元のasyncio.sleepを保存
_original_sleep = asyncio.sleep


class SleepMock:
    """asyncio.sleepのモッククラス

    call_args_listをプロパティとして動的に返すことで、
    テスト実行中に常に最新の呼び出し記録を参照できるようにする。
    """

    def __init__(self) -> None:
        self._call_records: list[tuple[float, tuple[Any, ...], dict[str, Any]]] = []

    @property
    def call_args_list(self) -> list[tuple[float, tuple[Any, ...], dict[str, Any]]]:
        """呼び出し記録を動的に返す"""
        return self._call_records

    def record_call(self, delay: float, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """呼び出しを記録"""
        self._call_records.append((delay, args, kwargs))

    def assert_any_call(self, *expected_args: Any, **expected_kwargs: Any) -> None:
        """指定した引数での呼び出しがあったことを検証

        unittest.mock.Mockのassert_any_callと同様に、
        位置引数とキーワード引数の両方をチェックする。
        """
        for delay, args, kwargs in self._call_records:
            actual_args = (delay,) + args
            if actual_args == expected_args and kwargs == expected_kwargs:
                return
        raise AssertionError(
            f"Expected call with args={expected_args}, kwargs={expected_kwargs} "
            f"not found in {self._call_records}"
        )

    def get_sleep_delays(self) -> list[float]:
        """記録されたsleep遅延時間のリストを取得

        テストでの検証を簡略化するためのヘルパーメソッド。
        """
        return [record[0] for record in self._call_records]


@pytest.fixture(autouse=True)
async def mock_asyncio_sleep() -> AsyncGenerator[SleepMock, None]:
    """asyncio.sleepをモックして即座に完了させる

    テストの実行時間を短縮するため、すべてのテストでasyncio.sleepを
    モックします。実際のsleep時間は待機せず、即座に完了します。

    ただし、引数が0の場合はイベントループを回すために実際のsleepを使用します。

    モックされたsleepのcall_argsを検証することで、正しい遅延時間が
    設定されていることを確認できます。
    """
    mock_sleep = SleepMock()

    async def patched_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        """引数が0の場合は実際のsleepを使用し、それ以外はモック"""
        mock_sleep.record_call(delay, args, kwargs)
        if delay == 0:
            # イベントループを回すために実際のsleepを使用
            await _original_sleep(0)
        else:
            # 0以外の場合はモック（即座に完了）
            pass

    with patch("asyncio.sleep", patched_sleep):
        yield mock_sleep
