"""反応待機制御

メッセージ受信後、設定された時間だけ待機してから応答判定を行います。
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage

logger = get_logger(__name__)


class ResponseDelayController:
    """反応待機制御

    メッセージ受信後、設定された時間だけ待機してから応答判定を行います。
    待機中に他のユーザーからの反応があった場合、待機をキャンセルします。
    """

    DEFAULT_DELAY_SECONDS = 60

    def __init__(self, delay_seconds: int = DEFAULT_DELAY_SECONDS) -> None:
        """初期化

        Args:
            delay_seconds: 応答判定までの待機時間（秒）
        """
        self._delay_seconds = delay_seconds
        self._pending_tasks: dict[str, asyncio.Task[None]] = {}

        logger.info(
            "response_delay_controller_initialized",
            delay_seconds=delay_seconds,
        )

    @property
    def delay_seconds(self) -> int:
        """待機時間を取得"""
        return self._delay_seconds

    def schedule_response_check(
        self,
        message: SlackMessage,
        callback: Callable[[SlackMessage], Awaitable[Any]],
    ) -> None:
        """応答チェックをスケジュール

        既存のタスクがあればキャンセルし、新しい非同期タスクを作成します。

        Args:
            message: 対象のSlackメッセージ
            callback: 遅延後に実行するコールバック関数
        """
        task_key = self._make_task_key(message)

        # 既存のタスクがあればキャンセル
        if task_key in self._pending_tasks:
            existing_task = self._pending_tasks[task_key]
            existing_task.cancel()
            logger.debug(
                "existing_task_cancelled",
                task_key=task_key,
            )

        # 新しいタスクを作成
        task = asyncio.create_task(self._delayed_callback(message, callback, task_key))
        self._pending_tasks[task_key] = task

        logger.debug(
            "response_check_scheduled",
            task_key=task_key,
            delay_seconds=self._delay_seconds,
        )

    def cancel_response_check(self, message: SlackMessage) -> bool:
        """応答チェックをキャンセル

        Args:
            message: キャンセル対象のメッセージ

        Returns:
            キャンセルに成功した場合はTrue、タスクが存在しない場合はFalse
        """
        task_key = self._make_task_key(message)

        if task_key not in self._pending_tasks:
            logger.debug(
                "cancel_task_not_found",
                task_key=task_key,
            )
            return False

        task = self._pending_tasks.pop(task_key)
        task.cancel()

        logger.debug(
            "response_check_cancelled",
            task_key=task_key,
        )
        return True

    async def _delayed_callback(
        self,
        message: SlackMessage,
        callback: Callable[[SlackMessage], Awaitable[Any]],
        task_key: str,
    ) -> None:
        """遅延コールバック

        指定時間待機後にコールバックを実行します。
        キャンセルされた場合はCancelledErrorをハンドリングします。

        Args:
            message: 対象のSlackメッセージ
            callback: 実行するコールバック関数
            task_key: タスクのキー（クリーンアップ用）
        """
        try:
            await asyncio.sleep(self._delay_seconds)

            logger.debug(
                "executing_delayed_callback",
                task_key=task_key,
            )

            await callback(message)

            logger.info(
                "delayed_callback_completed",
                task_key=task_key,
            )
        except asyncio.CancelledError:
            logger.debug(
                "delayed_callback_cancelled",
                task_key=task_key,
            )
            raise
        finally:
            # タスクを削除
            self._pending_tasks.pop(task_key, None)

    def _make_task_key(self, message: SlackMessage) -> str:
        """タスクキーを生成

        Args:
            message: 対象のSlackメッセージ

        Returns:
            "channel_id:message_id" 形式のキー
        """
        return f"{message.channel_id}:{message.message_id}"

    def get_pending_count(self) -> int:
        """待機中のタスク数を取得

        Returns:
            待機中のタスク数
        """
        return len(self._pending_tasks)
