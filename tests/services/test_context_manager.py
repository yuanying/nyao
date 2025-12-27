"""コンテキスト管理サービスのテスト"""

from datetime import UTC, datetime, timedelta

import pytest

from nyao.core.models import SlackMessage
from nyao.services.context_manager import ContextManagerService


@pytest.fixture
def service() -> ContextManagerService:
    """テスト用サービス（デフォルト設定）"""
    return ContextManagerService()


@pytest.fixture
def service_with_short_expiry() -> ContextManagerService:
    """短い有効期限のサービス（テスト用）"""
    return ContextManagerService(max_context_age_seconds=60)


@pytest.fixture
def sample_message() -> SlackMessage:
    """テスト用SlackMessage（スレッドなし）"""
    return SlackMessage(
        message_id="msg-001",
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="テストメッセージ",
        timestamp=datetime.now(UTC),
        thread_ts=None,
    )


@pytest.fixture
def sample_thread_message() -> SlackMessage:
    """テスト用SlackMessage（スレッドあり）"""
    return SlackMessage(
        message_id="msg-002",
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="スレッド内メッセージ",
        timestamp=datetime.now(UTC),
        thread_ts="1234567890.123456",
    )


@pytest.fixture
def sample_parent_message() -> SlackMessage:
    """テスト用SlackMessage（スレッドの親メッセージ）"""
    return SlackMessage(
        message_id="1234567890.123456",  # 親メッセージのmessage_id
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="スレッドの親メッセージ",
        timestamp=datetime.now(UTC),
        thread_ts=None,  # 投稿時はthread_tsがない
    )


@pytest.fixture
def sample_reply_message() -> SlackMessage:
    """テスト用SlackMessage（返信メッセージ）"""
    return SlackMessage(
        message_id="msg-reply-001",  # message_id != thread_ts
        channel_id="C12345678",
        user_id="U12345678",
        user_name="testuser",
        text="返信メッセージ",
        timestamp=datetime.now(UTC),
        thread_ts="1234567890.123456",  # 親のmessage_id
    )


class TestContextManagerServiceInit:
    """初期化テスト"""

    def test_init_with_default_values(self) -> None:
        """デフォルト値で初期化できること"""
        service = ContextManagerService()
        assert service is not None
        assert service.max_context_age_seconds == 7776000  # 90日
        assert service.max_messages_per_context == 50
        assert service.max_channel_context_messages == 20

    def test_init_with_custom_max_context_age(self) -> None:
        """カスタムmax_context_age_secondsで初期化できること"""
        service = ContextManagerService(max_context_age_seconds=3600)
        assert service.max_context_age_seconds == 3600

    def test_init_with_custom_max_messages(self) -> None:
        """カスタムmax_messages_per_contextで初期化できること"""
        service = ContextManagerService(max_messages_per_context=100)
        assert service.max_messages_per_context == 100

    def test_init_with_custom_max_channel_messages(self) -> None:
        """カスタムmax_channel_context_messagesで初期化できること"""
        service = ContextManagerService(max_channel_context_messages=30)
        assert service.max_channel_context_messages == 30


class TestMakeContextKey:
    """コンテキストキー生成テスト"""

    def test_make_key_with_thread_ts(
        self,
        service: ContextManagerService,
    ) -> None:
        """スレッドコンテキストのキー形式"""
        key = service._make_context_key("C12345678", "1234567890.123456")
        assert key == "C12345678:1234567890.123456"

    def test_make_key_without_thread_ts(
        self,
        service: ContextManagerService,
    ) -> None:
        """チャンネルコンテキストのキー形式"""
        key = service._make_context_key("C12345678", None)
        assert key == "C12345678"


class TestAddMessage:
    """メッセージ追加テスト"""

    def test_add_message_creates_new_context(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """新規コンテキストが自動作成されること"""
        service.add_message(sample_message)

        key = service._make_context_key(sample_message.channel_id, sample_message.thread_ts)
        assert key in service._contexts
        assert len(service._contexts[key].messages) == 1

    def test_add_thread_message_creates_thread_context(
        self,
        service: ContextManagerService,
        sample_thread_message: SlackMessage,
    ) -> None:
        """スレッドメッセージがスレッドコンテキストに追加されること"""
        service.add_message(sample_thread_message)

        key = service._make_context_key(
            sample_thread_message.channel_id, sample_thread_message.thread_ts
        )
        assert key in service._contexts
        context = service._contexts[key]
        assert context.thread_ts == sample_thread_message.thread_ts

    def test_add_channel_message_to_channel_context(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """チャンネルメッセージがチャンネルコンテキストに追加されること"""
        service.add_message(sample_message)

        key = service._make_context_key(sample_message.channel_id, None)
        assert key in service._contexts
        context = service._contexts[key]
        assert context.thread_ts is None
        assert len(context.messages) == 1

    def test_add_multiple_messages_to_same_context(
        self,
        service: ContextManagerService,
    ) -> None:
        """同じコンテキストに複数メッセージを追加できること"""
        msg1 = SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="メッセージ1",
            timestamp=datetime.now(UTC),
            thread_ts=None,
        )
        msg2 = SlackMessage(
            message_id="msg-002",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="メッセージ2",
            timestamp=datetime.now(UTC),
            thread_ts=None,
        )

        service.add_message(msg1)
        service.add_message(msg2)

        key = service._make_context_key("C12345678", None)
        assert len(service._contexts[key].messages) == 2

    def test_message_limit_removes_old_messages(self) -> None:
        """メッセージ数上限超過時に古いメッセージが削除されること"""
        service = ContextManagerService(max_messages_per_context=3)

        for i in range(5):
            msg = SlackMessage(
                message_id=f"msg-{i:03d}",
                channel_id="C12345678",
                user_id="U12345678",
                user_name="testuser",
                text=f"メッセージ{i}",
                timestamp=datetime.now(UTC),
                thread_ts="1234567890.123456",
            )
            service.add_message(msg)

        key = service._make_context_key("C12345678", "1234567890.123456")
        context = service._contexts[key]
        assert len(context.messages) == 3
        # 最初の2メッセージが削除され、最後の3つが残る
        assert context.messages[0].message_id == "msg-002"
        assert context.messages[2].message_id == "msg-004"

    def test_channel_message_limit_removes_old_messages(self) -> None:
        """チャンネルコンテキストのメッセージ数上限が機能すること"""
        service = ContextManagerService(max_channel_context_messages=2)

        for i in range(4):
            msg = SlackMessage(
                message_id=f"msg-{i:03d}",
                channel_id="C12345678",
                user_id="U12345678",
                user_name="testuser",
                text=f"メッセージ{i}",
                timestamp=datetime.now(UTC),
                thread_ts=None,  # チャンネルメッセージ
            )
            service.add_message(msg)

        key = service._make_context_key("C12345678", None)
        context = service._contexts[key]
        assert len(context.messages) == 2
        # 最初の2メッセージが削除され、最後の2つが残る
        assert context.messages[0].message_id == "msg-002"
        assert context.messages[1].message_id == "msg-003"

    def test_thread_message_not_added_to_channel_context(
        self,
        service: ContextManagerService,
        sample_thread_message: SlackMessage,
    ) -> None:
        """スレッドメッセージがチャンネルコンテキストに追加されないこと"""
        service.add_message(sample_thread_message)

        # チャンネルコンテキストは作成されない
        channel_key = service._make_context_key(sample_thread_message.channel_id, None)
        assert channel_key not in service._contexts

        # スレッドコンテキストは作成される
        thread_key = service._make_context_key(
            sample_thread_message.channel_id, sample_thread_message.thread_ts
        )
        assert thread_key in service._contexts

    def test_reply_copies_parent_to_thread_context(
        self,
        service: ContextManagerService,
        sample_parent_message: SlackMessage,
        sample_reply_message: SlackMessage,
    ) -> None:
        """返信時に親メッセージがスレッドコンテキストにコピーされること"""
        # 親メッセージを追加（チャンネルコンテキストに入る）
        service.add_message(sample_parent_message)

        # 返信メッセージを追加（スレッドコンテキストが作成される）
        service.add_message(sample_reply_message)

        # スレッドコンテキストを取得
        thread_context = service.get_context(
            sample_reply_message.channel_id,
            sample_reply_message.thread_ts,
        )

        assert thread_context is not None
        # 親メッセージ + 返信メッセージ = 2件
        assert len(thread_context.messages) == 2
        # 最初は親メッセージ
        assert thread_context.messages[0].message_id == sample_parent_message.message_id
        assert thread_context.messages[0].text == sample_parent_message.text
        # 2番目は返信メッセージ
        assert thread_context.messages[1].message_id == sample_reply_message.message_id

    def test_reply_without_parent_in_channel(
        self,
        service: ContextManagerService,
        sample_reply_message: SlackMessage,
    ) -> None:
        """親メッセージがチャンネルコンテキストにない場合でもエラーにならないこと"""
        # 親メッセージなしで返信を追加
        service.add_message(sample_reply_message)

        # スレッドコンテキストを取得
        thread_context = service.get_context(
            sample_reply_message.channel_id,
            sample_reply_message.thread_ts,
        )

        assert thread_context is not None
        # 返信メッセージのみ
        assert len(thread_context.messages) == 1
        assert thread_context.messages[0].message_id == sample_reply_message.message_id

    def test_parent_not_duplicated_on_second_reply(
        self,
        service: ContextManagerService,
        sample_parent_message: SlackMessage,
        sample_reply_message: SlackMessage,
    ) -> None:
        """2つ目の返信で親メッセージが重複しないこと"""
        # 親メッセージを追加
        service.add_message(sample_parent_message)

        # 1つ目の返信
        service.add_message(sample_reply_message)

        # 2つ目の返信
        second_reply = SlackMessage(
            message_id="msg-reply-002",
            channel_id=sample_reply_message.channel_id,
            user_id="U12345678",
            user_name="testuser",
            text="2つ目の返信",
            timestamp=datetime.now(UTC),
            thread_ts=sample_reply_message.thread_ts,
        )
        service.add_message(second_reply)

        # スレッドコンテキストを取得
        thread_context = service.get_context(
            sample_reply_message.channel_id,
            sample_reply_message.thread_ts,
        )

        assert thread_context is not None
        # 親メッセージ + 返信2件 = 3件（親は1回のみ）
        assert len(thread_context.messages) == 3
        assert thread_context.messages[0].message_id == sample_parent_message.message_id
        assert thread_context.messages[1].message_id == sample_reply_message.message_id
        assert thread_context.messages[2].message_id == second_reply.message_id

    def test_channel_message_stays_in_channel_only(
        self,
        service: ContextManagerService,
        sample_parent_message: SlackMessage,
    ) -> None:
        """スレッドなしメッセージはチャンネルコンテキストにのみ追加されること"""
        service.add_message(sample_parent_message)

        # チャンネルコンテキストに追加されている
        channel_context = service.get_channel_context(sample_parent_message.channel_id)
        assert channel_context is not None
        assert len(channel_context.messages) == 1

        # スレッドコンテキストは存在しない
        thread_context = service.get_context(
            sample_parent_message.channel_id,
            sample_parent_message.message_id,  # thread_tsとして使用してもNone
        )
        # スレッドコンテキストは作成されない（親メッセージのthread_ts=Noneなので）
        assert thread_context is None


class TestGetContext:
    """コンテキスト取得テスト"""

    def test_get_existing_thread_context(
        self,
        service: ContextManagerService,
        sample_thread_message: SlackMessage,
    ) -> None:
        """存在するスレッドコンテキストを取得できること"""
        service.add_message(sample_thread_message)

        context = service.get_context(
            sample_thread_message.channel_id, sample_thread_message.thread_ts
        )

        assert context is not None
        assert context.thread_ts == sample_thread_message.thread_ts
        assert len(context.messages) == 1

    def test_get_nonexistent_context_returns_none(
        self,
        service: ContextManagerService,
    ) -> None:
        """存在しないコンテキストはNoneを返すこと"""
        context = service.get_context("C99999999", "9999999999.999999")
        assert context is None

    def test_get_expired_context_returns_none_and_deletes(
        self,
        service_with_short_expiry: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """期限切れコンテキストはNoneを返し削除されること"""
        service = service_with_short_expiry
        service.add_message(sample_message)

        # コンテキストのlast_updatedを過去に設定
        key = service._make_context_key(sample_message.channel_id, sample_message.thread_ts)
        service._contexts[key].last_updated = datetime.now(UTC) - timedelta(seconds=120)

        # 取得するとNoneが返り、コンテキストが削除される
        context = service.get_context(sample_message.channel_id, sample_message.thread_ts)
        assert context is None
        assert key not in service._contexts


class TestGetChannelContext:
    """チャンネルコンテキスト取得テスト"""

    def test_get_existing_channel_context(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """存在するチャンネルコンテキストを取得できること"""
        service.add_message(sample_message)

        context = service.get_channel_context(sample_message.channel_id)

        assert context is not None
        assert context.thread_ts is None
        assert len(context.messages) == 1

    def test_get_channel_context_excludes_thread_messages(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
        sample_thread_message: SlackMessage,
    ) -> None:
        """チャンネルコンテキストにスレッドメッセージが含まれないこと"""
        service.add_message(sample_message)
        service.add_message(sample_thread_message)

        channel_context = service.get_channel_context(sample_message.channel_id)

        assert channel_context is not None
        # チャンネルコンテキストにはスレッドなしメッセージのみ
        assert len(channel_context.messages) == 1
        assert channel_context.messages[0].thread_ts is None

    def test_get_nonexistent_channel_context_returns_none(
        self,
        service: ContextManagerService,
    ) -> None:
        """存在しないチャンネルコンテキストはNoneを返すこと"""
        context = service.get_channel_context("C99999999")
        assert context is None


class TestIsContextExpired:
    """期限切れ判定テスト"""

    def test_fresh_context_is_not_expired(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """最近更新されたコンテキストは期限切れでないこと"""
        service.add_message(sample_message)

        key = service._make_context_key(sample_message.channel_id, sample_message.thread_ts)
        context = service._contexts[key]

        assert service._is_context_expired(context) is False

    def test_old_context_is_expired(
        self,
        service_with_short_expiry: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """古いコンテキストは期限切れであること"""
        service = service_with_short_expiry
        service.add_message(sample_message)

        key = service._make_context_key(sample_message.channel_id, sample_message.thread_ts)
        context = service._contexts[key]
        # last_updatedを過去に設定
        context.last_updated = datetime.now(UTC) - timedelta(seconds=120)

        assert service._is_context_expired(context) is True


class TestCleanupExpiredContexts:
    """クリーンアップテスト"""

    def test_cleanup_removes_expired_contexts(
        self,
        service_with_short_expiry: ContextManagerService,
    ) -> None:
        """期限切れコンテキストが削除されること"""
        service = service_with_short_expiry

        # メッセージを追加
        msg = SlackMessage(
            message_id="msg-001",
            channel_id="C12345678",
            user_id="U12345678",
            user_name="testuser",
            text="テストメッセージ",
            timestamp=datetime.now(UTC),
            thread_ts=None,
        )
        service.add_message(msg)

        # コンテキストのlast_updatedを過去に設定
        key = service._make_context_key("C12345678", None)
        service._contexts[key].last_updated = datetime.now(UTC) - timedelta(seconds=120)

        # クリーンアップ実行
        deleted = service.cleanup_expired_contexts()

        assert deleted == 1
        assert key not in service._contexts

    def test_cleanup_keeps_valid_contexts(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """有効なコンテキストは保持されること"""
        service.add_message(sample_message)

        deleted = service.cleanup_expired_contexts()

        assert deleted == 0
        key = service._make_context_key(sample_message.channel_id, sample_message.thread_ts)
        assert key in service._contexts

    def test_cleanup_returns_correct_count(
        self,
        service_with_short_expiry: ContextManagerService,
    ) -> None:
        """削除数が正確にカウントされること"""
        service = service_with_short_expiry

        # 3つのコンテキストを作成
        for i in range(3):
            msg = SlackMessage(
                message_id=f"msg-{i:03d}",
                channel_id=f"C{i:08d}",
                user_id="U12345678",
                user_name="testuser",
                text=f"メッセージ{i}",
                timestamp=datetime.now(UTC),
                thread_ts=None,
            )
            service.add_message(msg)

        # 2つを期限切れに設定
        keys = list(service._contexts.keys())
        for key in keys[:2]:
            service._contexts[key].last_updated = datetime.now(UTC) - timedelta(seconds=120)

        deleted = service.cleanup_expired_contexts()

        assert deleted == 2
        assert len(service._contexts) == 1

    def test_cleanup_with_no_contexts_returns_zero(
        self,
        service: ContextManagerService,
    ) -> None:
        """コンテキストがない場合は0を返すこと"""
        deleted = service.cleanup_expired_contexts()
        assert deleted == 0


class TestGetStatistics:
    """統計情報取得テスト"""

    def test_get_statistics_structure(
        self,
        service: ContextManagerService,
    ) -> None:
        """統計情報の構造が正しいこと"""
        stats = service.get_statistics()

        assert "context_count" in stats
        assert "max_context_age_seconds" in stats
        assert "max_messages_per_context" in stats
        assert "max_channel_context_messages" in stats

    def test_get_statistics_context_count(
        self,
        service: ContextManagerService,
        sample_message: SlackMessage,
    ) -> None:
        """コンテキスト数が正確にカウントされること"""
        # 最初は0
        stats = service.get_statistics()
        assert stats["context_count"] == 0

        # メッセージ追加後は1
        service.add_message(sample_message)
        stats = service.get_statistics()
        assert stats["context_count"] == 1

    def test_get_statistics_includes_settings(
        self,
        service: ContextManagerService,
    ) -> None:
        """設定値が含まれること"""
        stats = service.get_statistics()

        assert stats["max_context_age_seconds"] == 7776000
        assert stats["max_messages_per_context"] == 50
        assert stats["max_channel_context_messages"] == 20
