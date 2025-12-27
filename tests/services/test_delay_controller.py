"""反応待機制御のテスト"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from nyao.core.models import SlackMessage
from nyao.services.delay_controller import ResponseDelayController


@pytest.fixture
def controller() -> ResponseDelayController:
    """テスト用コントローラ（デフォルト設定）"""
    return ResponseDelayController()


@pytest.fixture
def controller_short_delay() -> ResponseDelayController:
    """短い遅延のコントローラ（テスト用）"""
    return ResponseDelayController(delay_seconds=1)


@pytest.fixture
def sample_message() -> SlackMessage:
    """テスト用SlackMessage"""
    return SlackMessage(
        message_id="msg-001",
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="テストメッセージ",
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def another_message() -> SlackMessage:
    """別のテスト用SlackMessage"""
    return SlackMessage(
        message_id="msg-002",
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="別のメッセージ",
        timestamp=datetime.now(UTC),
    )


class TestResponseDelayControllerInit:
    """初期化テスト"""

    def test_init_with_default_values(self) -> None:
        """デフォルト値で初期化できること"""
        controller = ResponseDelayController()
        assert controller is not None
        assert controller.delay_seconds == 60

    def test_init_with_custom_delay(self) -> None:
        """カスタムdelay_secondsで初期化できること"""
        controller = ResponseDelayController(delay_seconds=120)
        assert controller.delay_seconds == 120

    def test_init_pending_tasks_empty(self) -> None:
        """初期状態で待機中タスクが空であること"""
        controller = ResponseDelayController()
        assert controller.get_pending_count() == 0


class TestMakeTaskKey:
    """タスクキー生成テスト"""

    def test_make_task_key(self, controller: ResponseDelayController) -> None:
        """タスクキーが正しく生成されること"""
        message = SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="テスト",
            timestamp=datetime.now(UTC),
        )
        key = controller._make_task_key(message)
        assert key == "C12345678:msg-001"

    def test_make_task_key_different_channel(self, controller: ResponseDelayController) -> None:
        """異なるチャンネルで異なるキーが生成されること"""
        message1 = SlackMessage(
            message_id="msg-001",
            channel_id="C11111111",
            user_id="U12345678",
            user_name="testuser",
            text="テスト",
            timestamp=datetime.now(UTC),
        )
        message2 = SlackMessage(
            message_id="msg-001",
            channel_id="C22222222",
            user_id="U12345678",
            user_name="testuser",
            text="テスト",
            timestamp=datetime.now(UTC),
        )
        key1 = controller._make_task_key(message1)
        key2 = controller._make_task_key(message2)
        assert key1 != key2
        assert key1 == "C11111111:msg-001"
        assert key2 == "C22222222:msg-001"


class TestScheduleResponseCheck:
    """スケジューリングテスト"""

    async def test_schedule_creates_task(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """スケジュールでタスクが作成されること"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)

        assert controller_short_delay.get_pending_count() == 1

        # クリーンアップ
        controller_short_delay.cancel_response_check(sample_message)

    async def test_schedule_replaces_existing_task(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """既存タスクがある場合に置き換えられること"""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        controller_short_delay.schedule_response_check(sample_message, callback1)
        controller_short_delay.schedule_response_check(sample_message, callback2)

        # タスク数は1のまま
        assert controller_short_delay.get_pending_count() == 1

        # クリーンアップ
        controller_short_delay.cancel_response_check(sample_message)

    async def test_schedule_multiple_messages(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
        another_message: SlackMessage,
    ) -> None:
        """複数メッセージのスケジュールが独立して管理されること"""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        controller_short_delay.schedule_response_check(sample_message, callback1)
        controller_short_delay.schedule_response_check(another_message, callback2)

        assert controller_short_delay.get_pending_count() == 2

        # クリーンアップ
        controller_short_delay.cancel_response_check(sample_message)
        controller_short_delay.cancel_response_check(another_message)


class TestCancelResponseCheck:
    """キャンセルテスト"""

    async def test_cancel_existing_task(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """既存タスクがキャンセルできること"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)

        result = controller_short_delay.cancel_response_check(sample_message)

        assert result is True
        # 少し待ってタスクのクリーンアップを確認
        await asyncio.sleep(0.1)
        assert controller_short_delay.get_pending_count() == 0

    async def test_cancel_nonexistent_task(
        self,
        controller: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """存在しないタスクのキャンセルはFalseを返すこと"""
        result = controller.cancel_response_check(sample_message)
        assert result is False

    async def test_cancel_prevents_callback(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """キャンセルによりコールバックが実行されないこと"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)
        controller_short_delay.cancel_response_check(sample_message)

        # 遅延時間を超えて待機
        await asyncio.sleep(1.5)

        callback.assert_not_called()


class TestDelayedCallback:
    """遅延コールバックテスト"""

    async def test_callback_executed_after_delay(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
        mock_asyncio_sleep: AsyncMock,
    ) -> None:
        """遅延後にコールバックが実行されること"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)

        # タスクがスケジュールされたことを確認
        assert controller_short_delay.get_pending_count() == 1

        # イベントループを回してタスクを完了させる
        # （asyncio.sleepがモックされているため即座に完了）
        await asyncio.sleep(0)

        # コールバックが実行されること
        callback.assert_called_once_with(sample_message)

        # 正しい遅延時間でsleepが呼ばれたことを確認
        mock_asyncio_sleep.assert_any_call(controller_short_delay.delay_seconds)

    async def test_callback_receives_correct_message(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """コールバックに正しいメッセージが渡されること"""
        received_message = None

        async def capture_callback(msg: SlackMessage) -> None:
            nonlocal received_message
            received_message = msg

        controller_short_delay.schedule_response_check(sample_message, capture_callback)

        # イベントループを回してタスクを完了させる
        await asyncio.sleep(0)

        assert received_message is not None
        assert received_message.message_id == sample_message.message_id
        assert received_message.channel_id == sample_message.channel_id

    async def test_task_removed_after_completion(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """コールバック完了後にタスクが削除されること"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)

        assert controller_short_delay.get_pending_count() == 1

        # イベントループを回してタスクを完了させる
        await asyncio.sleep(0)

        assert controller_short_delay.get_pending_count() == 0


class TestGetPendingCount:
    """待機中タスク数テスト"""

    def test_pending_count_initial(self, controller: ResponseDelayController) -> None:
        """初期状態で0であること"""
        assert controller.get_pending_count() == 0

    async def test_pending_count_after_schedule(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """スケジュール後にカウントが増加すること"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)

        assert controller_short_delay.get_pending_count() == 1

        # クリーンアップ
        controller_short_delay.cancel_response_check(sample_message)

    async def test_pending_count_after_cancel(
        self,
        controller_short_delay: ResponseDelayController,
        sample_message: SlackMessage,
    ) -> None:
        """キャンセル後にカウントが減少すること"""
        callback = AsyncMock()
        controller_short_delay.schedule_response_check(sample_message, callback)
        controller_short_delay.cancel_response_check(sample_message)

        await asyncio.sleep(0.1)
        assert controller_short_delay.get_pending_count() == 0
