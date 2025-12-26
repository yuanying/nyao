"""Slack接続管理モジュール

Slack APIへの接続を確立し、Socket Modeでリアルタイムイベントを受信します。
"""

from collections.abc import Awaitable, Callable
from typing import Any

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from nyao.core.logging import get_logger
from nyao.core.models import SlackMessage
from nyao.integrations.slack.event_receiver import EventReceiver

logger = get_logger(__name__)

# 型定義
MessageHandler = Callable[[SlackMessage], Awaitable[None]]
ReactionHandler = Callable[[dict[str, Any]], Awaitable[None]]


class SlackConnectionManager:
    """Slack Socket Mode接続の管理を担当

    Socket Modeを使用してSlackからのイベントをリアルタイムで受信し、
    登録されたハンドラに配信します。
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
    ) -> None:
        """初期化

        Args:
            bot_token: Slack Bot User OAuth Token
            app_token: Slack App-Level Token（Socket Mode用）
        """
        self._bot_token = bot_token
        self._app_token = app_token
        self._bot_user_id = ""
        self._message_handlers: list[MessageHandler] = []
        self._reaction_handlers: list[ReactionHandler] = []

        # Slack Boltアプリを初期化
        self._app = AsyncApp(token=bot_token)
        self._socket_handler: AsyncSocketModeHandler | None = None
        self._event_receiver: EventReceiver | None = None

        # イベントハンドラを登録
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """イベントハンドラをSlack Appに登録"""

        @self._app.event("message")
        async def handle_message(event: dict, say: Any) -> None:
            """メッセージイベントハンドラ"""
            if self._event_receiver is None:
                logger.warning("event_receiver_not_initialized")
                return

            slack_message = await self._event_receiver.handle_message_event(event, say)
            if slack_message is None:
                return

            # 登録されたハンドラに配信
            for handler in self._message_handlers:
                try:
                    await handler(slack_message)
                except Exception as e:
                    logger.error(
                        "message_handler_error",
                        handler=getattr(handler, "__name__", repr(handler)),
                        error=str(e),
                    )

        @self._app.event("reaction_added")
        async def handle_reaction(event: dict) -> None:
            """リアクション追加イベントハンドラ"""
            if self._event_receiver is None:
                logger.warning("event_receiver_not_initialized")
                return

            reaction_info = await self._event_receiver.handle_reaction_event(event)
            if reaction_info is None:
                return

            # 登録されたハンドラに配信
            for handler in self._reaction_handlers:
                try:
                    await handler(reaction_info)
                except Exception as e:
                    logger.error(
                        "reaction_handler_error",
                        handler=getattr(handler, "__name__", repr(handler)),
                        error=str(e),
                    )

    async def start(self) -> None:
        """Socket Mode接続を開始"""
        logger.info("starting_slack_connection")

        # Bot User IDを取得
        auth_response = await self._app.client.auth_test()
        self._bot_user_id = auth_response.get("user_id", "")
        logger.info("bot_user_id_retrieved", bot_user_id=self._bot_user_id)

        # EventReceiverを初期化
        self._event_receiver = EventReceiver(self._app.client, self._bot_user_id)

        # Socket Modeハンドラを開始
        self._socket_handler = AsyncSocketModeHandler(self._app, self._app_token)
        await self._socket_handler.start_async()

        logger.info("slack_connection_started")

    async def stop(self) -> None:
        """Socket Mode接続を停止"""
        logger.info("stopping_slack_connection")

        if self._socket_handler is not None:
            await self._socket_handler.close_async()
            self._socket_handler = None

        logger.info("slack_connection_stopped")

    def register_message_handler(self, handler: MessageHandler) -> None:
        """メッセージハンドラを登録

        Args:
            handler: メッセージ受信時に呼び出されるコールバック
        """
        self._message_handlers.append(handler)
        logger.debug(
            "message_handler_registered",
            handler=getattr(handler, "__name__", repr(handler)),
        )

    def register_reaction_handler(self, handler: ReactionHandler) -> None:
        """リアクションハンドラを登録

        Args:
            handler: リアクション追加時に呼び出されるコールバック
        """
        self._reaction_handlers.append(handler)
        logger.debug(
            "reaction_handler_registered",
            handler=getattr(handler, "__name__", repr(handler)),
        )

    @property
    def client(self) -> AsyncWebClient:
        """WebClientインスタンスを取得"""
        return self._app.client

    @property
    def bot_user_id(self) -> str:
        """Bot自身のユーザーIDを取得"""
        return self._bot_user_id
