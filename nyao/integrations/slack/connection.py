"""Slack接続管理

Socket Modeを使用したSlack APIへの接続を管理します。
"""

from collections.abc import Awaitable, Callable
from typing import Any

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.logging import get_logger

logger = get_logger(__name__)


class SlackConnectionManager:
    """Slack Socket Mode接続を管理するクラス"""

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        monitored_channels: list[str] | None = None,
    ) -> None:
        """SlackConnectionManagerを初期化

        Args:
            bot_token: Slack Bot User OAuth Token
            app_token: Slack App-Level Token
            monitored_channels: 監視対象チャンネルIDのリスト
        """
        self._bot_token = bot_token
        self._app_token = app_token
        self._monitored_channels = monitored_channels
        self._bot_user_id: str | None = None
        self._handler: AsyncSocketModeHandler | None = None
        self._logger = get_logger(__name__)

        # AsyncAppの初期化
        self._app = AsyncApp(token=bot_token)

    @property
    def app(self) -> AsyncApp:
        """Boltアプリケーションインスタンスを取得"""
        return self._app

    @property
    def client(self) -> AsyncWebClient:
        """AsyncWebClientインスタンスを取得"""
        return self._app.client

    @property
    def bot_user_id(self) -> str | None:
        """Bot自身のユーザーIDを取得"""
        return self._bot_user_id

    @property
    def monitored_channels(self) -> list[str] | None:
        """監視対象チャンネルのリストを取得"""
        return self._monitored_channels

    def register_message_handler(
        self,
        handler: Callable[[dict, Callable[..., Awaitable[Any]]], Awaitable[None]],
    ) -> None:
        """メッセージイベントハンドラを登録

        Args:
            handler: async def handler(event: dict, say: Callable) -> None
        """
        self._app.event("message")(handler)
        self._logger.info("message_handler_registered")

    def register_reaction_handler(
        self,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
        """リアクションイベントハンドラを登録

        Args:
            handler: async def handler(event: dict) -> None
        """
        self._app.event("reaction_added")(handler)
        self._logger.info("reaction_handler_registered")

    async def start(self) -> None:
        """Socket Mode接続を開始"""
        self._logger.info("slack_connection_starting")

        # Bot自身のユーザーIDを取得
        auth_response = await self._app.client.auth_test()
        self._bot_user_id = auth_response.get("user_id")
        self._logger.info("bot_user_id_fetched", bot_user_id=self._bot_user_id)

        # Socket Mode接続を開始
        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        await self._handler.start_async()

        self._logger.info("slack_connection_started")

    async def stop(self) -> None:
        """Socket Mode接続を停止"""
        if self._handler is not None:
            self._logger.info("slack_connection_stopping")
            await self._handler.close_async()
            self._handler = None
            self._logger.info("slack_connection_stopped")
