"""SlackConnectionManagerのテスト"""

from unittest.mock import AsyncMock, MagicMock, patch

from nyao.core.models import SlackMessage
from nyao.integrations.slack.connection import SlackConnectionManager


class TestSlackConnectionManager:
    """SlackConnectionManagerのテスト"""

    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_init(
        self,
        mock_async_app_class: MagicMock,
    ) -> None:
        """初期化"""
        mock_app = MagicMock()
        mock_async_app_class.return_value = mock_app

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        assert manager._bot_token == "xoxb-test-token"
        assert manager._app_token == "xapp-test-token"
        mock_async_app_class.assert_called_once_with(token="xoxb-test-token")

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_start(
        self,
        mock_async_app_class: MagicMock,
        mock_socket_handler_class: MagicMock,
    ) -> None:
        """接続開始"""
        mock_app = MagicMock()
        mock_app.client = AsyncMock()
        mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U_BOT_ID"})
        mock_async_app_class.return_value = mock_app

        mock_handler = AsyncMock()
        mock_handler.start_async = AsyncMock()
        mock_socket_handler_class.return_value = mock_handler

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        await manager.start()

        mock_app.client.auth_test.assert_called_once()
        mock_socket_handler_class.assert_called_once_with(mock_app, "xapp-test-token")
        mock_handler.start_async.assert_called_once()
        assert manager.bot_user_id == "U_BOT_ID"

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_stop(
        self,
        mock_async_app_class: MagicMock,
        mock_socket_handler_class: MagicMock,
    ) -> None:
        """接続停止"""
        mock_app = MagicMock()
        mock_app.client = AsyncMock()
        mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U_BOT_ID"})
        mock_async_app_class.return_value = mock_app

        mock_handler = AsyncMock()
        mock_handler.start_async = AsyncMock()
        mock_handler.close_async = AsyncMock()
        mock_socket_handler_class.return_value = mock_handler

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        await manager.start()
        await manager.stop()

        mock_handler.close_async.assert_called_once()

    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_register_message_handler(
        self,
        mock_async_app_class: MagicMock,
    ) -> None:
        """メッセージハンドラ登録"""
        mock_app = MagicMock()
        mock_async_app_class.return_value = mock_app

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        async def test_handler(message: SlackMessage) -> None:
            pass

        manager.register_message_handler(test_handler)

        assert test_handler in manager._message_handlers

    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_register_reaction_handler(
        self,
        mock_async_app_class: MagicMock,
    ) -> None:
        """リアクションハンドラ登録"""
        mock_app = MagicMock()
        mock_async_app_class.return_value = mock_app

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        async def test_handler(reaction: dict) -> None:
            pass

        manager.register_reaction_handler(test_handler)

        assert test_handler in manager._reaction_handlers

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_client_property(
        self,
        mock_async_app_class: MagicMock,
        mock_socket_handler_class: MagicMock,
    ) -> None:
        """clientプロパティ"""
        mock_app = MagicMock()
        mock_client = AsyncMock()
        mock_app.client = mock_client
        mock_async_app_class.return_value = mock_app

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        assert manager.client == mock_client

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_connection_manager_bot_user_id_before_start(
        self,
        mock_async_app_class: MagicMock,
        mock_socket_handler_class: MagicMock,
    ) -> None:
        """start前はbot_user_idが空文字"""
        mock_app = MagicMock()
        mock_async_app_class.return_value = mock_app

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        assert manager.bot_user_id == ""

    @patch("nyao.integrations.slack.connection.AsyncApp")
    async def test_multiple_message_handlers(
        self,
        mock_async_app_class: MagicMock,
    ) -> None:
        """複数のメッセージハンドラが登録できる"""
        mock_app = MagicMock()
        mock_async_app_class.return_value = mock_app

        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

        async def handler1(message: SlackMessage) -> None:
            pass

        async def handler2(message: SlackMessage) -> None:
            pass

        manager.register_message_handler(handler1)
        manager.register_message_handler(handler2)

        assert len(manager._message_handlers) == 2
        assert handler1 in manager._message_handlers
        assert handler2 in manager._message_handlers
