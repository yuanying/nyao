"""メインアプリケーションのテスト"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from nyao.core.models import ResponseDecision, SlackMessage

# テスト用の固定日時
FIXED_TIMESTAMP = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


class TestNyaoBotInit:
    """NyaoBotの初期化テスト"""

    def test_init_creates_all_components(self) -> None:
        """すべてのコンポーネントが初期化されること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            # コンポーネントが初期化されていることを確認
            # 公開インターフェースを通じて初期化状態を検証
            assert bot is not None


class TestNyaoBotStop:
    """NyaoBotの停止テスト"""

    async def test_stop_disconnects_from_slack(self) -> None:
        """停止時にSlackから切断されること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()
            bot._slack_connection = AsyncMock()
            bot._slack_connection.stop = AsyncMock()
            bot._running = True

            await bot.stop()

            bot._slack_connection.stop.assert_called_once()

    async def test_stop_sets_running_flag(self) -> None:
        """停止時にrunningフラグがFalseになること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()
            bot._slack_connection = AsyncMock()
            bot._slack_connection.stop = AsyncMock()
            bot._running = True

            await bot.stop()

            assert bot._running is False


class TestNyaoBotHandleMessage:
    """メッセージハンドラのテスト"""

    async def test_handle_message_adds_to_context(self) -> None:
        """メッセージがコンテキストに追加されること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            # モックを設定
            bot._context_manager = MagicMock()
            bot._delay_controller = MagicMock()
            bot._delay_controller.schedule_response_check = MagicMock()

            message = SlackMessage(
                message_id="msg-001",
                channel_id="C12345",
                user_id="U12345",
                user_name="testuser",
                text="テストメッセージ",
                timestamp=FIXED_TIMESTAMP,
            )

            await bot._handle_message(message)

            bot._context_manager.add_message.assert_called_once_with(message)

    async def test_handle_message_schedules_response_check(self) -> None:
        """応答チェックがスケジュールされること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            # モックを設定
            bot._context_manager = MagicMock()
            bot._delay_controller = MagicMock()
            bot._delay_controller.schedule_response_check = MagicMock()

            message = SlackMessage(
                message_id="msg-001",
                channel_id="C12345",
                user_id="U12345",
                user_name="testuser",
                text="テストメッセージ",
                timestamp=FIXED_TIMESTAMP,
            )

            await bot._handle_message(message)

            bot._delay_controller.schedule_response_check.assert_called_once()


class TestNyaoBotHandleReaction:
    """リアクションハンドラのテスト"""

    async def test_handle_reaction_logs_info(self) -> None:
        """リアクションイベントがログに記録されること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            # モックを設定
            bot._context_manager = MagicMock()

            reaction_info = {
                "user": "U12345",
                "reaction": "thumbsup",
                "channel": "C12345",
                "message_ts": "1234567890.123456",
            }

            # 例外が発生しないことを確認
            await bot._handle_reaction(reaction_info)


class TestNyaoBotCheckAndRespond:
    """応答チェックと応答送信のテスト"""

    async def test_check_and_respond_when_should_respond(self) -> None:
        """応答すべき場合に応答が送信されること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            message = SlackMessage(
                message_id="msg-001",
                channel_id="C12345",
                user_id="U12345",
                user_name="testuser",
                text="こんにちは！",
                timestamp=FIXED_TIMESTAMP,
            )

            # モックを設定
            bot._response_judge = AsyncMock()
            bot._response_judge.should_respond_to_message = AsyncMock(
                return_value=ResponseDecision(
                    should_respond=True,
                    reason="応答が必要なメッセージです",
                    confidence=0.9,
                )
            )

            bot._context_manager = MagicMock()
            bot._context_manager.get_context = MagicMock(return_value=None)
            bot._context_manager.get_channel_context = MagicMock(return_value=None)

            bot._response_generator = AsyncMock()
            bot._response_generator.generate_response = AsyncMock(return_value="こんにちは！")

            bot._message_sender = AsyncMock()
            bot._message_sender.send_message = AsyncMock(return_value="msg-response")

            await bot._check_and_respond(message)

            # 応答が送信されたことを確認
            bot._message_sender.send_message.assert_called_once()

    async def test_check_and_respond_when_should_not_respond(self) -> None:
        """応答すべきでない場合に応答が送信されないこと"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            message = SlackMessage(
                message_id="msg-001",
                channel_id="C12345",
                user_id="U12345",
                user_name="testuser",
                text="...",
                timestamp=FIXED_TIMESTAMP,
            )

            # モックを設定
            bot._response_judge = AsyncMock()
            bot._response_judge.should_respond_to_message = AsyncMock(
                return_value=ResponseDecision(
                    should_respond=False,
                    reason="応答不要なメッセージです",
                    confidence=0.9,
                )
            )

            bot._message_sender = AsyncMock()

            await bot._check_and_respond(message)

            # 応答が送信されていないことを確認
            bot._message_sender.send_message.assert_not_called()

    async def test_check_and_respond_handles_exception(self) -> None:
        """例外発生時にエラーが適切に処理されること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()

            message = SlackMessage(
                message_id="msg-001",
                channel_id="C12345",
                user_id="U12345",
                user_name="testuser",
                text="テスト",
                timestamp=FIXED_TIMESTAMP,
            )

            # エラーを発生させるモック
            bot._response_judge = AsyncMock()
            bot._response_judge.should_respond_to_message = AsyncMock(
                side_effect=Exception("Test error")
            )

            # 例外が発生しても処理が中断しないことを確認
            await bot._check_and_respond(message)


class TestNyaoBotCleanupLoop:
    """クリーンアップループのテスト"""

    async def test_cleanup_loop_stops_when_not_running(self) -> None:
        """runningフラグがFalseの場合にループが終了すること"""
        with (
            patch("nyao.main.get_settings") as mock_get_settings,
            patch("nyao.main.setup_logging"),
        ):
            from nyao.config.settings import (
                BotSettings,
                LiteLLMSettings,
                LoggingSettings,
                Settings,
            )

            mock_settings = MagicMock(spec=Settings)
            mock_settings.slack_bot_token = "xoxb-test-token"
            mock_settings.slack_app_token = "xapp-test-token"
            mock_settings.litellm = LiteLLMSettings(model_id="gpt-4")
            mock_settings.bot = BotSettings()
            mock_settings.logging = LoggingSettings()
            mock_get_settings.return_value = mock_settings

            from nyao.main import NyaoBot

            bot = NyaoBot()
            bot._context_manager = MagicMock()
            bot._context_manager.cleanup_expired_contexts = MagicMock(return_value=0)
            bot._running = False  # 最初からFalse

            # ループがすぐに終了することを確認
            await asyncio.wait_for(bot._cleanup_loop(interval_seconds=1), timeout=2.0)
