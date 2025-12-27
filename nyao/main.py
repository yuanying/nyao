"""メインアプリケーション

すべてのコンポーネントを統合し、アプリケーションのエントリーポイントを提供します。
"""

import asyncio
import functools
import signal
from typing import Any

from nyao.config.settings import get_response_delay_with_jitter, get_settings
from nyao.core.logging import get_logger, setup_logging
from nyao.core.models import SlackMessage
from nyao.integrations.llm.generator_agent import ResponseGeneratorAgent
from nyao.integrations.llm.judge_agent import ResponseJudgeAgent
from nyao.integrations.slack.channel_fetcher import ChannelHistoryFetcher
from nyao.integrations.slack.connection import SlackConnectionManager
from nyao.integrations.slack.message_sender import MessageSender
from nyao.integrations.slack.thread_fetcher import ThreadHistoryFetcher
from nyao.services.context_manager import ContextManagerService
from nyao.services.delay_controller import ResponseDelayController
from nyao.services.response_generator import ResponseGeneratorService
from nyao.services.response_judge import ResponseJudgeService

logger = get_logger(__name__)

CLEANUP_INTERVAL_SECONDS = 300  # 5分


class NyaoBot:
    """Nyao Slackボットのメインクラス

    すべてのコンポーネントを統合し、アプリケーションのライフサイクルを管理します。
    """

    def __init__(self) -> None:
        """すべてのコンポーネントを初期化"""
        settings = get_settings()

        # ロギングを初期化
        setup_logging()

        logger.info("nyao_bot_initializing")

        # Slack連携コンポーネント
        self._slack_connection = SlackConnectionManager(
            bot_token=settings.slack_bot_token,
            app_token=settings.slack_app_token,
        )
        self._message_sender: MessageSender | None = None
        self._thread_fetcher: ThreadHistoryFetcher | None = None
        self._channel_fetcher: ChannelHistoryFetcher | None = None

        # LLM連携コンポーネント
        persona = settings.bot.persona
        self._judge_agent = ResponseJudgeAgent(
            settings=settings.litellm,
            persona=persona,
        )
        self._generator_agent = ResponseGeneratorAgent(
            settings=settings.litellm,
            persona=persona,
        )

        # サービスレイヤー
        self._response_judge = ResponseJudgeService(
            judge_agent=self._judge_agent,
            response_delay=settings.bot.response_delay.base,
        )
        self._response_generator = ResponseGeneratorService(
            generator_agent=self._generator_agent,
        )
        self._context_manager = ContextManagerService()
        self._delay_controller = ResponseDelayController(
            delay_seconds=get_response_delay_with_jitter(),
        )

        self._running = False

        logger.info("nyao_bot_initialized")

    async def start(self) -> None:
        """アプリケーションを起動"""
        logger.info("nyao_bot_starting")

        # 各コンポーネントにWebClientを設定（Socket Mode開始前に初期化）
        self._message_sender = MessageSender(self._slack_connection.client)
        self._thread_fetcher = ThreadHistoryFetcher(self._slack_connection.client)
        self._channel_fetcher = ChannelHistoryFetcher(self._slack_connection.client)

        # イベントハンドラを登録
        self._slack_connection.register_message_handler(self._handle_message)
        self._slack_connection.register_reaction_handler(self._handle_reaction)

        # Slack接続を開始（イベント受信が始まる）
        await self._slack_connection.start()

        self._running = True

        logger.info("nyao_bot_started")

        # クリーンアップループを起動
        cleanup_task = asyncio.create_task(self._cleanup_loop())

        # 実行中ループ
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("nyao_bot_cancelled")
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        """アプリケーションを停止"""
        logger.info("nyao_bot_stopping")

        self._running = False

        # Slack接続を停止
        await self._slack_connection.stop()

        logger.info("nyao_bot_stopped")

    async def _handle_message(self, message: SlackMessage) -> None:
        """メッセージイベントハンドラ

        Args:
            message: 受信したSlackメッセージ
        """
        logger.debug(
            "handle_message",
            message_id=message.message_id,
            channel_id=message.channel_id,
            user_id=message.user_id,
        )

        # メッセージをコンテキストに追加
        self._context_manager.add_message(message)

        # 応答チェックをスケジュール
        self._delay_controller.schedule_response_check(message, self._check_and_respond)

        logger.debug(
            "message_handled",
            message_id=message.message_id,
        )

    async def _handle_reaction(self, reaction_info: dict[str, Any]) -> None:
        """リアクションイベントハンドラ

        Args:
            reaction_info: リアクション情報
        """
        logger.debug(
            "handle_reaction",
            user=reaction_info.get("user"),
            reaction=reaction_info.get("reaction"),
            channel=reaction_info.get("channel"),
            message_ts=reaction_info.get("message_ts"),
        )

    async def _check_and_respond(self, message: SlackMessage) -> None:
        """応答チェックと応答送信

        Args:
            message: チェック対象のメッセージ
        """
        logger.debug(
            "check_and_respond_start",
            message_id=message.message_id,
        )

        try:
            # 応答判定
            decision = await self._response_judge.should_respond_to_message(
                message=message,
                reactions=message.reactions,
                reply_count=message.reply_count,
            )

            if not decision.should_respond:
                logger.info(
                    "decided_not_to_respond",
                    message_id=message.message_id,
                    reason=decision.reason,
                )
                return

            # コンテキストを取得
            thread_context = None
            channel_context = None

            if message.thread_ts:
                thread_context = self._context_manager.get_context(
                    channel_id=message.channel_id,
                    thread_ts=message.thread_ts,
                )
            else:
                channel_context = self._context_manager.get_channel_context(
                    channel_id=message.channel_id,
                )

            # 応答を生成
            response = await self._response_generator.generate_response(
                message=message,
                thread_context=thread_context,
                channel_context=channel_context,
            )

            # 応答を送信
            if self._message_sender is None:
                logger.error("message_sender_not_initialized")
                return

            # スレッドに返信するか、チャンネルに返信するか
            thread_ts = message.thread_ts or message.message_id

            await self._message_sender.send_message(
                channel_id=message.channel_id,
                text=response,
                thread_ts=thread_ts,
            )

            logger.info(
                "response_sent",
                message_id=message.message_id,
                response_length=len(response),
            )

        except Exception as e:
            logger.error(
                "check_and_respond_error",
                message_id=message.message_id,
                error=str(e),
            )

    async def _cleanup_loop(self, interval_seconds: int = CLEANUP_INTERVAL_SECONDS) -> None:
        """定期クリーンアップループ

        Args:
            interval_seconds: クリーンアップ間隔（秒）
        """
        logger.info("cleanup_loop_started", interval_seconds=interval_seconds)

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)

                if not self._running:
                    break

                # 期限切れコンテキストをクリーンアップ
                deleted_count = self._context_manager.cleanup_expired_contexts()
                if deleted_count > 0:
                    logger.info("cleanup_completed", deleted_count=deleted_count)

            except asyncio.CancelledError:
                logger.info("cleanup_loop_cancelled")
                break
            except Exception as e:
                logger.error("cleanup_loop_error", error=str(e))

        logger.info("cleanup_loop_stopped")


async def main() -> None:
    """メインエントリーポイント"""
    bot = NyaoBot()

    # シグナルハンドラを設定
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler(sig: signal.Signals) -> None:
        logger.info("signal_received", signal=sig.name)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, functools.partial(signal_handler, sig))

    try:
        # bot.start()をバックグラウンドで起動し、シャットダウンイベントを待つ
        start_task = asyncio.create_task(bot.start())

        # シャットダウンイベントを待つ
        await shutdown_event.wait()

        # 停止処理
        await bot.stop()

        # start_taskをキャンセル
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass
    except asyncio.CancelledError:
        logger.info("main_cancelled")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
