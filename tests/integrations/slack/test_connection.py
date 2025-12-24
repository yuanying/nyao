"""SlackConnectionManager のテスト"""

from unittest.mock import AsyncMock, patch

import pytest

from nyao.integrations.slack.connection import SlackConnectionManager


class TestSlackConnectionManager:
    """SlackConnectionManager のテスト"""

    @pytest.fixture
    def connection_manager(self):
        """SlackConnectionManager インスタンス"""
        return SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
            monitored_channels=["C123456", "C789012"],
        )

    def test_init_with_valid_tokens(self, connection_manager):
        """有効なトークンで初期化できること"""
        assert connection_manager is not None
        assert connection_manager._bot_token == "xoxb-test-token"
        assert connection_manager._app_token == "xapp-test-token"
        assert connection_manager._monitored_channels == ["C123456", "C789012"]

    def test_init_without_monitored_channels(self):
        """監視チャンネルなしで初期化できること"""
        manager = SlackConnectionManager(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )
        assert manager._monitored_channels is None

    def test_app_property(self, connection_manager):
        """appプロパティでAsyncAppインスタンスを取得できること"""
        app = connection_manager.app
        assert app is not None

    def test_client_property(self, connection_manager):
        """clientプロパティでAsyncWebClientインスタンスを取得できること"""
        client = connection_manager.client
        assert client is not None

    def test_register_message_handler(self, connection_manager):
        """メッセージハンドラを登録できること"""

        async def handler(event, say):
            pass

        # エラーが発生しないことを確認
        connection_manager.register_message_handler(handler)

    def test_register_reaction_handler(self, connection_manager):
        """リアクションハンドラを登録できること"""

        async def handler(event):
            pass

        # エラーが発生しないことを確認
        connection_manager.register_reaction_handler(handler)

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    async def test_start_establishes_connection(self, mock_handler_class, connection_manager):
        """start()で接続が確立されること"""
        mock_handler = AsyncMock()
        mock_handler.start_async = AsyncMock()
        mock_handler_class.return_value = mock_handler

        # auth.testのモック
        connection_manager._app.client.auth_test = AsyncMock(
            return_value={"ok": True, "user_id": "UBOT123"}
        )

        await connection_manager.start()

        mock_handler_class.assert_called_once()
        mock_handler.start_async.assert_called_once()

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    async def test_stop_disconnects(self, mock_handler_class, connection_manager):
        """stop()で接続が切断されること"""
        mock_handler = AsyncMock()
        mock_handler.start_async = AsyncMock()
        mock_handler.close_async = AsyncMock()
        mock_handler_class.return_value = mock_handler

        # auth.testのモック
        connection_manager._app.client.auth_test = AsyncMock(
            return_value={"ok": True, "user_id": "UBOT123"}
        )

        await connection_manager.start()
        await connection_manager.stop()

        mock_handler.close_async.assert_called_once()

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    async def test_stop_without_start(self, mock_handler_class, connection_manager):
        """start()なしでstop()を呼んでもエラーにならないこと"""
        # エラーが発生しないことを確認
        await connection_manager.stop()

    def test_bot_user_id_property(self, connection_manager):
        """bot_user_idプロパティがNoneで初期化されること"""
        assert connection_manager.bot_user_id is None

    @patch("nyao.integrations.slack.connection.AsyncSocketModeHandler")
    async def test_start_fetches_bot_user_id(self, mock_handler_class, connection_manager):
        """start()でBot自身のユーザーIDを取得すること"""
        mock_handler = AsyncMock()
        mock_handler.start_async = AsyncMock()
        mock_handler_class.return_value = mock_handler

        # auth.testのモック
        connection_manager._app.client.auth_test = AsyncMock(
            return_value={"ok": True, "user_id": "UBOT123"}
        )

        await connection_manager.start()

        assert connection_manager.bot_user_id == "UBOT123"

    def test_monitored_channels_property(self, connection_manager):
        """monitored_channelsプロパティで監視チャンネルを取得できること"""
        assert connection_manager.monitored_channels == ["C123456", "C789012"]
