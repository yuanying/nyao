# 階層的記憶管理 - サービス設計

## 概要

Phase 2.4では、階層的記憶管理システムのサービス層を実装します。各記憶層（ワーキングメモリ、短期記憶、長期記憶）へのアクセスを抽象化し、プロンプトコンテキストの構築を行います。

## 実装優先度

**高** - データモデル（03-memory-models.md）の実装後に実装

## 依存関係

### 依存先
- Phase 2.4: データモデル（03-memory-models.md）
- Phase 2.1: LiteLLM直接使用（NyaoAgent）

### 依存元
- Phase 2.4: バッチ処理（05-batch-processing.md）
- NyaoBot（main.py）

---

## コンポーネント

### 1. WorkingMemoryService - ワーキングメモリサービス

#### 目的

ワーキングメモリ（過去X日分のメッセージ）の保存・取得・管理を行います。

#### 機能要件

- **FR-101**: ワーキングメモリとして過去x日分のメッセージを保持
- **FR-104**: チャンネル・スレッドごとの記憶を独立して管理

#### 実装方針

SlackMessageをWorkingMemoryMessageに変換してデータベースに保存し、LiteLLMメッセージ形式で取得できるようにします。

#### 主要インターフェース

```python
class WorkingMemoryService:
    """ワーキングメモリサービス"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        retention_days: int = 7,
    ) -> None:
        """
        ワーキングメモリサービスを初期化する。

        Args:
            db_manager: データベースマネージャー
            retention_days: メッセージ保持日数
        """

    async def save_message(self, message: SlackMessage) -> WorkingMemoryMessage:
        """
        Slackメッセージを保存する。

        Args:
            message: Slackメッセージ

        Returns:
            WorkingMemoryMessage: 保存されたメッセージ
        """

    async def save_bot_response(
        self,
        channel_id: str,
        thread_ts: str | None,
        content: str,
        message_ts: str,
    ) -> WorkingMemoryMessage:
        """
        ボットの応答を保存する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ
            content: 応答内容
            message_ts: メッセージタイムスタンプ

        Returns:
            WorkingMemoryMessage: 保存されたメッセージ
        """

    async def get_messages_for_context(
        self,
        channel_id: str,
        thread_ts: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, str]]:
        """
        LiteLLMメッセージ形式でメッセージを取得する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ（Noneの場合はチャンネル全体）
            limit: 取得するメッセージ数の上限

        Returns:
            list[dict[str, str]]: LiteLLMメッセージ形式のリスト
                [{"role": "user", "content": "..."}, ...]
        """

    async def get_recent_messages(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[WorkingMemoryMessage]:
        """
        最近のメッセージを取得する。

        Args:
            channel_id: チャンネルID
            since: この日時以降のメッセージを取得
            limit: 取得するメッセージ数の上限

        Returns:
            list[WorkingMemoryMessage]: メッセージのリスト
        """

    async def cleanup_old_messages(self) -> int:
        """
        古いメッセージを削除する。

        Returns:
            int: 削除されたメッセージ数
        """

    def _convert_to_litellm_format(
        self,
        messages: list[WorkingMemoryMessage],
    ) -> list[dict[str, str]]:
        """
        WorkingMemoryMessageをLiteLLMメッセージ形式に変換する。
        """
```

#### テスト要件

- [ ] メッセージが正しく保存されること
- [ ] ボットの応答が正しく保存されること
- [ ] LiteLLMメッセージ形式で取得できること
- [ ] チャンネル・スレッドごとにフィルタリングされること
- [ ] 古いメッセージが削除されること

---

### 2. ShortTermMemoryService - 短期記憶サービス

#### 目的

短期記憶（スレッド要約、チャンネル日次要約）の保存・取得・管理を行います。

#### 機能要件

- **FR-101**: 短期記憶としてスレッド要約、チャンネル日次要約を保持
- **FR-103**: 記憶を自動的に要約・圧縮

#### 主要インターフェース

```python
class ShortTermMemoryService:
    """短期記憶サービス"""

    def __init__(self, db_manager: DatabaseManager) -> None:
        """
        短期記憶サービスを初期化する。

        Args:
            db_manager: データベースマネージャー
        """

    # スレッド要約

    async def get_thread_summary(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> ThreadSummary | None:
        """
        スレッド要約を取得する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ

        Returns:
            ThreadSummary | None: スレッド要約（存在しない場合はNone）
        """

    async def save_thread_summary(
        self,
        summary: ThreadSummary,
    ) -> ThreadSummary:
        """
        スレッド要約を保存する（作成または更新）。

        Args:
            summary: スレッド要約

        Returns:
            ThreadSummary: 保存されたスレッド要約
        """

    async def get_active_thread_summaries(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 10,
    ) -> list[ThreadSummary]:
        """
        アクティブなスレッド要約を取得する。

        Args:
            channel_id: チャンネルID
            since: この日時以降のスレッドを取得
            limit: 取得するスレッド数の上限

        Returns:
            list[ThreadSummary]: スレッド要約のリスト
        """

    # チャンネル日次要約

    async def get_channel_daily_summary(
        self,
        channel_id: str,
        target_date: date,
    ) -> ChannelDailySummary | None:
        """
        チャンネル日次要約を取得する。

        Args:
            channel_id: チャンネルID
            target_date: 対象日付

        Returns:
            ChannelDailySummary | None: 日次要約（存在しない場合はNone）
        """

    async def save_channel_daily_summary(
        self,
        summary: ChannelDailySummary,
    ) -> ChannelDailySummary:
        """
        チャンネル日次要約を保存する（作成または更新）。

        Args:
            summary: チャンネル日次要約

        Returns:
            ChannelDailySummary: 保存された日次要約
        """

    async def get_recent_daily_summaries(
        self,
        channel_id: str,
        days: int = 7,
    ) -> list[ChannelDailySummary]:
        """
        最近のチャンネル日次要約を取得する。

        Args:
            channel_id: チャンネルID
            days: 取得する日数

        Returns:
            list[ChannelDailySummary]: 日次要約のリスト（新しい順）
        """

    async def get_missing_daily_summary_dates(
        self,
        channel_id: str,
        days: int = 7,
    ) -> list[date]:
        """
        日次要約が存在しない日付のリストを取得する。

        Args:
            channel_id: チャンネルID
            days: チェックする日数

        Returns:
            list[date]: 日次要約が存在しない日付のリスト
        """
```

#### テスト要件

- [ ] スレッド要約が正しく保存・取得されること
- [ ] チャンネル日次要約が正しく保存・取得されること
- [ ] 最近の要約が正しくフィルタリングされること
- [ ] 欠落している日次要約の日付が取得できること

---

### 3. LongTermMemoryService - 長期記憶サービス

#### 目的

長期記憶（ワークスペース記憶、チャンネル特性、ユーザー特性）の保存・取得・管理を行います。

#### 機能要件

- **FR-101**: 長期記憶としてワークスペース要約、チャンネル特性、ユーザー特性を保持
- **FR-105**: ユーザーごとの特性や好みを長期記憶に保存

#### 主要インターフェース

```python
class LongTermMemoryService:
    """長期記憶サービス"""

    def __init__(self, db_manager: DatabaseManager) -> None:
        """
        長期記憶サービスを初期化する。

        Args:
            db_manager: データベースマネージャー
        """

    # ワークスペース記憶

    async def get_workspace_memory(self) -> WorkspaceMemory:
        """
        ワークスペース記憶を取得する（なければ作成）。

        Returns:
            WorkspaceMemory: ワークスペース記憶
        """

    async def save_workspace_memory(
        self,
        memory: WorkspaceMemory,
    ) -> WorkspaceMemory:
        """
        ワークスペース記憶を保存する。

        Args:
            memory: ワークスペース記憶

        Returns:
            WorkspaceMemory: 保存されたワークスペース記憶
        """

    # チャンネル長期記憶

    async def get_channel_memory(
        self,
        channel_id: str,
    ) -> ChannelLongTermMemory | None:
        """
        チャンネル長期記憶を取得する。

        Args:
            channel_id: チャンネルID

        Returns:
            ChannelLongTermMemory | None: チャンネル長期記憶
        """

    async def save_channel_memory(
        self,
        memory: ChannelLongTermMemory,
    ) -> ChannelLongTermMemory:
        """
        チャンネル長期記憶を保存する（作成または更新）。

        Args:
            memory: チャンネル長期記憶

        Returns:
            ChannelLongTermMemory: 保存されたチャンネル長期記憶
        """

    async def get_all_channel_memories(self) -> list[ChannelLongTermMemory]:
        """
        すべてのチャンネル長期記憶を取得する。

        Returns:
            list[ChannelLongTermMemory]: チャンネル長期記憶のリスト
        """

    # ユーザー長期記憶

    async def get_user_memory(
        self,
        user_id: str,
    ) -> UserLongTermMemory | None:
        """
        ユーザー長期記憶を取得する。

        Args:
            user_id: ユーザーID

        Returns:
            UserLongTermMemory | None: ユーザー長期記憶
        """

    async def save_user_memory(
        self,
        memory: UserLongTermMemory,
    ) -> UserLongTermMemory:
        """
        ユーザー長期記憶を保存する（作成または更新）。

        Args:
            memory: ユーザー長期記憶

        Returns:
            UserLongTermMemory: 保存されたユーザー長期記憶
        """

    async def get_user_memories_for_channel(
        self,
        channel_id: str,
        user_ids: list[str],
    ) -> list[UserLongTermMemory]:
        """
        指定されたユーザーの長期記憶を取得する。

        Args:
            channel_id: チャンネルID（フィルタリング用）
            user_ids: ユーザーIDのリスト

        Returns:
            list[UserLongTermMemory]: ユーザー長期記憶のリスト
        """
```

#### テスト要件

- [ ] ワークスペース記憶が正しく保存・取得されること
- [ ] チャンネル長期記憶が正しく保存・取得されること
- [ ] ユーザー長期記憶が正しく保存・取得されること

---

### 4. MemoryContextBuilder - プロンプトコンテキスト構築

#### 目的

階層的記憶を組み合わせて、プロンプト用のコンテキストを構築します。

#### 機能要件

- **FR-102**: 過去の会話履歴を参照して、コンテキストに応じた応答を生成
- **FR-103**: LLMのコンテキストウィンドウを効率的に使用

#### 実装方針

階層的記憶を以下の優先順位で組み合わせ、トークン数制限（8000トークン）内に収めます。

1. **長期記憶**（優先度: 高、圧縮率: 高）
   - ワークスペース全体の要約・特性
   - チャンネルの要約・特性

2. **短期記憶**（優先度: 中、圧縮率: 中）
   - チャンネル日次要約（過去x日分）
   - スレッド要約・タイトル

3. **ワーキングメモリ**（優先度: 高、圧縮率: 低）
   - 直近のメッセージ（生データ）

#### 主要インターフェース

```python
class MemoryContextBuilder:
    """階層的記憶からプロンプトコンテキストを構築"""

    DEFAULT_MAX_TOKENS: int = 8000
    TOKENS_PER_CHAR: float = 0.25  # 概算（日本語の場合）

    def __init__(
        self,
        working_memory: WorkingMemoryService,
        short_term: ShortTermMemoryService,
        long_term: LongTermMemoryService,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        """
        コンテキストビルダーを初期化する。

        Args:
            working_memory: ワーキングメモリサービス
            short_term: 短期記憶サービス
            long_term: 長期記憶サービス
            max_tokens: 最大トークン数
        """

    async def build_context(
        self,
        channel_id: str,
        thread_ts: str | None = None,
        include_user_memory: bool = True,
    ) -> MemoryContext:
        """
        プロンプト用のコンテキストを構築する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ
            include_user_memory: ユーザー記憶を含めるか

        Returns:
            MemoryContext: 構築されたコンテキスト
        """

    async def build_messages_for_llm(
        self,
        channel_id: str,
        thread_ts: str | None = None,
    ) -> list[dict[str, str]]:
        """
        LLM用のメッセージリストを構築する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ

        Returns:
            list[dict[str, str]]: LLMメッセージ形式のリスト
        """

    def _estimate_tokens(self, text: str) -> int:
        """
        テキストのトークン数を推定する。

        Args:
            text: テキスト

        Returns:
            int: 推定トークン数
        """

    def _truncate_to_token_limit(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> list[dict[str, str]]:
        """
        トークン制限に収まるようにメッセージを切り詰める。
        古いメッセージから削除する。

        Args:
            messages: メッセージリスト
            max_tokens: 最大トークン数

        Returns:
            list[dict[str, str]]: 切り詰められたメッセージリスト
        """

    async def _build_long_term_context(
        self,
        channel_id: str,
    ) -> str:
        """長期記憶からコンテキストを構築する"""

    async def _build_short_term_context(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> str:
        """短期記憶からコンテキストを構築する"""

    async def _build_working_memory_context(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> list[dict[str, str]]:
        """ワーキングメモリからコンテキストを構築する"""
```

#### MemoryContext データクラス

```python
@dataclass
class MemoryContext:
    """記憶コンテキスト"""

    # 長期記憶
    workspace_summary: str
    channel_summary: str
    channel_characteristics: str

    # 短期記憶
    recent_daily_summaries: list[str]
    thread_summaries: list[str]

    # ワーキングメモリ
    recent_messages: list[dict[str, str]]

    # メタデータ
    total_tokens: int
    truncated: bool

    def to_system_prompt_section(self) -> str:
        """システムプロンプト用のセクションに変換する"""

    def to_messages(self) -> list[dict[str, str]]:
        """LLMメッセージ形式に変換する"""
```

#### テスト要件

- [ ] コンテキストが正しく構築されること
- [ ] トークン数制限が守られること
- [ ] 階層的記憶が正しい優先順位で組み込まれること
- [ ] 古いメッセージから切り詰められること

---

## 既存サービスとの統合

### ContextManagerServiceからの移行

Phase 1の`ContextManagerService`はインメモリでコンテキストを管理していました。Phase 2では、以下のように段階的に移行します。

1. **WorkingMemoryService**がメッセージの永続化を担当
2. **MemoryContextBuilder**がコンテキスト構築を担当
3. **ContextManagerService**は廃止または薄いラッパーとして維持

```python
# services/context_manager.py の更新

class ContextManagerService:
    """コンテキスト管理サービス（Phase 2対応）"""

    def __init__(
        self,
        working_memory: WorkingMemoryService,
        context_builder: MemoryContextBuilder,
    ) -> None:
        self._working_memory = working_memory
        self._context_builder = context_builder

    async def add_message(self, message: SlackMessage) -> None:
        """メッセージを追加する（DBに保存）"""
        await self._working_memory.save_message(message)

    async def get_context(
        self,
        channel_id: str,
        thread_ts: str | None = None,
    ) -> MemoryContext:
        """コンテキストを取得する"""
        return await self._context_builder.build_context(
            channel_id=channel_id,
            thread_ts=thread_ts,
        )
```

---

## ディレクトリ構成

```
nyao/
├── memory/
│   ├── __init__.py
│   ├── models.py              # データモデル（03-memory-models.md）
│   ├── database.py            # DatabaseManager
│   ├── working_memory.py      # WorkingMemoryService
│   ├── short_term.py          # ShortTermMemoryService
│   ├── long_term.py           # LongTermMemoryService
│   └── context_builder.py     # MemoryContextBuilder
├── services/
│   └── context_manager.py     # 更新（Phase 2対応）
```

---

## 実装タスク

### Day 3: WorkingMemoryServiceの実装

- [ ] `memory/working_memory.py` の作成
- [ ] `save_message()` の実装
- [ ] `save_bot_response()` の実装
- [ ] `get_messages_for_context()` の実装
- [ ] `cleanup_old_messages()` の実装
- [ ] テストの作成・実行

### Day 4: ShortTermMemoryServiceとLongTermMemoryServiceの実装

- [ ] `memory/short_term.py` の作成
- [ ] `memory/long_term.py` の作成
- [ ] 各メソッドの実装
- [ ] テストの作成・実行

### Day 5: MemoryContextBuilderの実装

- [ ] `memory/context_builder.py` の作成
- [ ] `build_context()` の実装
- [ ] `build_messages_for_llm()` の実装
- [ ] トークン数推定・制限の実装
- [ ] テストの作成・実行
- [ ] ContextManagerServiceの更新

---

## テスト戦略

### ユニットテスト

```python
# tests/memory/test_working_memory.py

@pytest.mark.asyncio
async def test_save_and_get_message(db_manager):
    """メッセージの保存と取得"""
    service = WorkingMemoryService(db_manager)
    message = create_test_slack_message()
    await service.save_message(message)
    messages = await service.get_messages_for_context(
        channel_id=message.channel_id,
    )
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_cleanup_old_messages(db_manager):
    """古いメッセージの削除"""


# tests/memory/test_context_builder.py

@pytest.mark.asyncio
async def test_build_context_within_token_limit(memory_services):
    """トークン制限内でコンテキストが構築されること"""
    builder = MemoryContextBuilder(**memory_services)
    context = await builder.build_context(channel_id="C123")
    assert context.total_tokens <= 8000


@pytest.mark.asyncio
async def test_truncate_old_messages(memory_services):
    """古いメッセージが切り詰められること"""
```

---

## 完了条件

- [ ] WorkingMemoryServiceが実装されていること
- [ ] ShortTermMemoryServiceが実装されていること
- [ ] LongTermMemoryServiceが実装されていること
- [ ] MemoryContextBuilderが実装されていること
- [ ] トークン数制限が守られること（8000トークン以内）
- [ ] ContextManagerServiceがPhase 2対応に更新されていること
- [ ] 全テストがパスすること
- [ ] ruff、tyによるチェックがパスすること
