"""コンテキスト管理サービス

チャンネルおよびスレッドごとの会話コンテキストをインメモリで管理します。
"""

from datetime import UTC, datetime

from nyao.core.logging import get_logger
from nyao.core.models import ConversationContext, SlackMessage

logger = get_logger(__name__)


class ContextManagerService:
    """コンテキスト管理サービス

    チャンネルおよびスレッドごとの会話コンテキストをインメモリで管理します。
    """

    DEFAULT_MAX_CONTEXT_AGE_SECONDS = 7776000  # 90日
    DEFAULT_MAX_MESSAGES_PER_CONTEXT = 50
    DEFAULT_MAX_CHANNEL_CONTEXT_MESSAGES = 20

    def __init__(
        self,
        max_context_age_seconds: int = DEFAULT_MAX_CONTEXT_AGE_SECONDS,
        max_messages_per_context: int = DEFAULT_MAX_MESSAGES_PER_CONTEXT,
        max_channel_context_messages: int = DEFAULT_MAX_CHANNEL_CONTEXT_MESSAGES,
    ) -> None:
        """初期化

        Args:
            max_context_age_seconds: コンテキストの最大保持期間（秒）
            max_messages_per_context: スレッドコンテキストあたりの最大メッセージ数
            max_channel_context_messages: チャンネルコンテキストの最大メッセージ数
        """
        self._max_context_age_seconds = max_context_age_seconds
        self._max_messages_per_context = max_messages_per_context
        self._max_channel_context_messages = max_channel_context_messages
        self._contexts: dict[str, ConversationContext] = {}

        logger.info(
            "context_manager_service_initialized",
            max_context_age_seconds=max_context_age_seconds,
            max_messages_per_context=max_messages_per_context,
            max_channel_context_messages=max_channel_context_messages,
        )

    @property
    def max_context_age_seconds(self) -> int:
        """コンテキストの最大保持期間を取得"""
        return self._max_context_age_seconds

    @property
    def max_messages_per_context(self) -> int:
        """スレッドコンテキストあたりの最大メッセージ数を取得"""
        return self._max_messages_per_context

    @property
    def max_channel_context_messages(self) -> int:
        """チャンネルコンテキストの最大メッセージ数を取得"""
        return self._max_channel_context_messages

    def _make_context_key(self, channel_id: str, thread_ts: str | None) -> str:
        """コンテキストキーを生成

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドのタイムスタンプ

        Returns:
            コンテキストキー（"channel_id:thread_ts" または "channel_id"）
        """
        if thread_ts:
            return f"{channel_id}:{thread_ts}"
        return channel_id

    def add_message(self, message: SlackMessage) -> None:
        """メッセージをコンテキストに追加

        スレッドメッセージの場合はスレッドコンテキストに追加。
        スレッドに属さないメッセージの場合はチャンネルコンテキストに追加。
        スレッドコンテキストが新規作成される場合、チャンネルコンテキストから親メッセージをコピー。
        新規コンテキストは自動作成され、メッセージ数が上限を超えたら古いものから削除。

        Args:
            message: 追加するSlackMessage
        """
        if message.thread_ts is None:
            # 通常メッセージ → チャンネルコンテキストに追加
            self._add_to_context(message.channel_id, None, message)
        else:
            # スレッドメッセージ
            thread_key = self._make_context_key(message.channel_id, message.thread_ts)

            # スレッドコンテキストが新規の場合、親メッセージをコピー
            if thread_key not in self._contexts:
                self._copy_parent_to_thread_context(message.channel_id, message.thread_ts)

            # スレッドコンテキストに追加
            self._add_to_context(message.channel_id, message.thread_ts, message)

    def _add_to_context(
        self,
        channel_id: str,
        thread_ts: str | None,
        message: SlackMessage,
    ) -> None:
        """指定コンテキストにメッセージを追加（共通処理）

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドのタイムスタンプ（Noneの場合はチャンネルレベル）
            message: 追加するSlackMessage
        """
        key = self._make_context_key(channel_id, thread_ts)

        # コンテキストが存在しない場合は新規作成
        if key not in self._contexts:
            self._contexts[key] = ConversationContext(
                channel_id=channel_id,
                thread_ts=thread_ts,
                messages=[],
                last_updated=datetime.now(UTC),
            )
            logger.debug(
                "context_created",
                key=key,
                channel_id=channel_id,
                thread_ts=thread_ts,
            )

        context = self._contexts[key]
        context.add_message(message)

        # メッセージ数上限チェック
        limit = (
            self._max_channel_context_messages
            if thread_ts is None
            else self._max_messages_per_context
        )
        while len(context.messages) > limit:
            removed = context.messages.pop(0)
            logger.debug(
                "message_removed_due_to_limit",
                key=key,
                removed_message_id=removed.message_id,
            )

        logger.debug(
            "message_added",
            key=key,
            message_id=message.message_id,
            message_count=len(context.messages),
        )

    def _copy_parent_to_thread_context(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> None:
        """チャンネルコンテキストから親メッセージを探してスレッドコンテキストにコピー

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドのタイムスタンプ（親メッセージのmessage_id）
        """
        channel_context = self.get_channel_context(channel_id)
        if channel_context is None:
            return

        # 親メッセージを探す（message_id == thread_ts）
        for msg in channel_context.messages:
            if msg.message_id == thread_ts:
                # スレッドコンテキストに親メッセージを追加
                self._add_to_context(channel_id, thread_ts, msg)
                logger.debug(
                    "parent_message_copied_to_thread",
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    parent_message_id=msg.message_id,
                )
                break

    def get_context(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> ConversationContext | None:
        """コンテキストを取得

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドのタイムスタンプ（Noneの場合はチャンネルレベル）

        Returns:
            ConversationContext: コンテキスト（存在しない場合または期限切れの場合はNone）
        """
        key = self._make_context_key(channel_id, thread_ts)

        if key not in self._contexts:
            return None

        context = self._contexts[key]

        # 期限切れチェック
        if self._is_context_expired(context):
            del self._contexts[key]
            logger.debug(
                "context_expired_and_deleted",
                key=key,
                channel_id=channel_id,
                thread_ts=thread_ts,
            )
            return None

        return context

    def get_channel_context(self, channel_id: str) -> ConversationContext | None:
        """チャンネルレベルのコンテキストを取得

        スレッドに属さないメッセージのみを含むコンテキストを返します。

        Args:
            channel_id: チャンネルID

        Returns:
            ConversationContext: チャンネルコンテキスト（存在しない場合または期限切れの場合はNone）
        """
        return self.get_context(channel_id, None)

    def _is_context_expired(self, context: ConversationContext) -> bool:
        """コンテキストが期限切れか判定

        Args:
            context: 判定対象のコンテキスト

        Returns:
            期限切れの場合True
        """
        elapsed = datetime.now(UTC) - context.last_updated
        return elapsed.total_seconds() > self._max_context_age_seconds

    def cleanup_expired_contexts(self) -> int:
        """期限切れのコンテキストをクリーンアップ

        Returns:
            削除されたコンテキストの数
        """
        expired_keys = [
            key for key, context in self._contexts.items() if self._is_context_expired(context)
        ]

        for key in expired_keys:
            del self._contexts[key]
            logger.debug("context_cleaned_up", key=key)

        if expired_keys:
            logger.info(
                "cleanup_expired_contexts_completed",
                deleted_count=len(expired_keys),
            )

        return len(expired_keys)

    def get_statistics(self) -> dict[str, int]:
        """統計情報を取得

        Returns:
            統計情報の辞書（context_count, max_context_age_seconds等）
        """
        return {
            "context_count": len(self._contexts),
            "max_context_age_seconds": self._max_context_age_seconds,
            "max_messages_per_context": self._max_messages_per_context,
            "max_channel_context_messages": self._max_channel_context_messages,
        }
