# 日次要約バッチ処理

## 概要

Phase 2.4では、日次要約バッチ処理を実装します。定期的にチャンネルの活動を要約し、短期記憶と長期記憶を更新します。

## 実装優先度

**中** - 記憶管理サービス（04-memory-services.md）の実装後に実装

## 依存関係

### 依存先
- Phase 2.4: 記憶管理サービス（04-memory-services.md）
- Phase 2.1: LiteLLM直接使用（NyaoAgent）

### 依存元
- NyaoBot（main.py）

---

## コンポーネント

### 1. MemorySummarizer - 記憶要約サービス

#### 目的

LLMを使用して、各種記憶の要約を生成します。

#### 機能要件

- **FR-103**: LLMのコンテキストウィンドウを効率的に使用するため、記憶を自動的に要約・圧縮

#### 主要インターフェース

```python
class MemorySummarizer:
    """記憶要約サービス"""

    def __init__(
        self,
        agent: NyaoAgent,
        working_memory: WorkingMemoryService,
        short_term: ShortTermMemoryService,
        long_term: LongTermMemoryService,
    ) -> None:
        """
        記憶要約サービスを初期化する。

        Args:
            agent: LLMエージェント
            working_memory: ワーキングメモリサービス
            short_term: 短期記憶サービス
            long_term: 長期記憶サービス
        """

    # スレッド要約

    async def summarize_thread(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> ThreadSummary:
        """
        スレッドを要約する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ

        Returns:
            ThreadSummary: 生成されたスレッド要約
        """

    async def should_update_thread_summary(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> bool:
        """
        スレッド要約を更新すべきか判定する。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ

        Returns:
            bool: 更新すべき場合True
        """

    # チャンネル日次要約

    async def summarize_channel_daily(
        self,
        channel_id: str,
        target_date: date,
    ) -> ChannelDailySummary:
        """
        チャンネルの日次要約を生成する。

        Args:
            channel_id: チャンネルID
            target_date: 対象日付

        Returns:
            ChannelDailySummary: 生成された日次要約
        """

    # 長期記憶の更新

    async def update_workspace_memory(self) -> WorkspaceMemory:
        """
        ワークスペース記憶を更新する。

        Returns:
            WorkspaceMemory: 更新されたワークスペース記憶
        """

    async def update_channel_long_term(
        self,
        channel_id: str,
    ) -> ChannelLongTermMemory:
        """
        チャンネル長期記憶を更新する。

        Args:
            channel_id: チャンネルID

        Returns:
            ChannelLongTermMemory: 更新されたチャンネル長期記憶
        """

    async def update_user_long_term(
        self,
        user_id: str,
    ) -> UserLongTermMemory:
        """
        ユーザー長期記憶を更新する。

        Args:
            user_id: ユーザーID

        Returns:
            UserLongTermMemory: 更新されたユーザー長期記憶
        """
```

#### テスト要件

- [ ] スレッド要約が正しく生成されること
- [ ] チャンネル日次要約が正しく生成されること
- [ ] ワークスペース記憶が正しく更新されること
- [ ] チャンネル長期記憶が正しく更新されること
- [ ] ユーザー長期記憶が正しく更新されること

---

### 2. 要約用プロンプトテンプレート

#### スレッド要約プロンプト

```python
THREAD_SUMMARY_PROMPT = """
以下のスレッドの会話を要約してください。

## 会話内容
{messages}

## 出力形式
JSON形式で以下を出力してください：
{
    "title": "スレッドのタイトル（20文字以内）",
    "summary": "スレッドの要約（200文字以内）",
    "key_topics": ["トピック1", "トピック2", ...],
    "is_resolved": true/false（質問や課題が解決したかどうか）
}
"""
```

#### チャンネル日次要約プロンプト

```python
CHANNEL_DAILY_SUMMARY_PROMPT = """
以下は{date}の{channel_name}チャンネルの活動です。

## メッセージ数
{message_count}件

## アクティブユーザー
{active_users}

## 主要なスレッド
{thread_summaries}

## 出力形式
JSON形式で以下を出力してください：
{
    "summary": "日次要約（300文字以内）",
    "topics": ["話題1", "話題2", ...],
    "mood": "チャンネルの雰囲気（例: 活発、落ち着いている、etc.）",
    "important_threads": ["thread_ts1", "thread_ts2", ...]
}
"""
```

#### チャンネル特性抽出プロンプト

```python
CHANNEL_CHARACTERISTICS_PROMPT = """
以下は{channel_name}チャンネルの過去の活動履歴です。

## 日次要約履歴
{daily_summaries}

## 現在のチャンネル特性（あれば）
{current_characteristics}

## 出力形式
JSON形式で以下を出力してください：
{
    "purpose": "チャンネルの目的",
    "typical_topics": ["よくある話題1", "話題2", ...],
    "historical_summary": "過去の重要な出来事の要約"
}
"""
```

#### ユーザー特性抽出プロンプト

```python
USER_CHARACTERISTICS_PROMPT = """
以下は{user_name}さんの過去のメッセージ履歴です。

## メッセージ履歴
{messages}

## 現在のユーザー特性（あれば）
{current_characteristics}

## 出力形式
JSON形式で以下を出力してください：
{
    "interests": ["興味1", "興味2", ...],
    "expertise": ["専門知識1", "スキル2", ...]
}
"""
```

---

### 3. BatchProcessor - バッチ処理

#### 目的

定期的に要約生成バッチ処理を実行します。

#### 機能要件

- 10分間隔で実行
- チャンネルごとに変更検知（最終更新時刻を追跡）
- 当日分: 変更があれば更新
- 過去X日分: 存在しなければ作成

#### 実装方針

```python
class BatchProcessor:
    """日次要約バッチ処理"""

    DEFAULT_INTERVAL_SECONDS: int = 600  # 10分
    DEFAULT_LOOKBACK_DAYS: int = 7

    def __init__(
        self,
        summarizer: MemorySummarizer,
        working_memory: WorkingMemoryService,
        short_term: ShortTermMemoryService,
        slack_client: SlackConnectionManager,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        self._summarizer = summarizer
        self._working_memory = working_memory
        self._short_term = short_term
        self._slack_client = slack_client
        self._interval_seconds = interval_seconds
        self._lookback_days = lookback_days
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_processed: dict[str, datetime] = {}
```

#### 主要インターフェース

```python
class BatchProcessor:
    """日次要約バッチ処理"""

    async def start(self) -> None:
        """
        バッチ処理ループを開始する。
        """

    async def stop(self) -> None:
        """
        バッチ処理ループを停止する。
        """

    async def run_once(self) -> BatchResult:
        """
        バッチ処理を1回実行する。

        Returns:
            BatchResult: 処理結果
        """

    async def _process_loop(self) -> None:
        """
        バッチ処理ループ（内部メソッド）。
        """

    async def _get_active_channels(self) -> list[str]:
        """
        アクティブなチャンネルIDのリストを取得する。

        Returns:
            list[str]: チャンネルIDのリスト
        """

    async def _process_channel(self, channel_id: str) -> ChannelBatchResult:
        """
        チャンネルの要約処理を実行する。

        Args:
            channel_id: チャンネルID

        Returns:
            ChannelBatchResult: 処理結果
        """

    async def _has_channel_changes(
        self,
        channel_id: str,
        since: datetime,
    ) -> bool:
        """
        チャンネルに変更があるか確認する。

        Args:
            channel_id: チャンネルID
            since: この日時以降の変更を確認

        Returns:
            bool: 変更がある場合True
        """

    async def _process_today_summary(
        self,
        channel_id: str,
    ) -> ChannelDailySummary | None:
        """
        当日の日次要約を処理する。

        Args:
            channel_id: チャンネルID

        Returns:
            ChannelDailySummary | None: 更新された場合は日次要約
        """

    async def _process_missing_summaries(
        self,
        channel_id: str,
    ) -> list[ChannelDailySummary]:
        """
        欠落している日次要約を処理する。

        Args:
            channel_id: チャンネルID

        Returns:
            list[ChannelDailySummary]: 作成された日次要約のリスト
        """

    async def _process_thread_summaries(
        self,
        channel_id: str,
    ) -> list[ThreadSummary]:
        """
        スレッド要約を処理する。

        Args:
            channel_id: チャンネルID

        Returns:
            list[ThreadSummary]: 更新されたスレッド要約のリスト
        """

    async def _update_long_term_memories(self) -> None:
        """
        長期記憶を更新する（低頻度で実行）。
        """
```

#### BatchResult データクラス

```python
@dataclass
class ChannelBatchResult:
    """チャンネルのバッチ処理結果"""
    channel_id: str
    today_summary_updated: bool
    missing_summaries_created: int
    thread_summaries_updated: int
    errors: list[str]


@dataclass
class BatchResult:
    """バッチ処理結果"""
    started_at: datetime
    completed_at: datetime
    channels_processed: int
    channel_results: list[ChannelBatchResult]
    long_term_updated: bool
    errors: list[str]

    @property
    def success(self) -> bool:
        """処理が成功したか"""
        return len(self.errors) == 0

    @property
    def duration_seconds(self) -> float:
        """処理時間（秒）"""
        return (self.completed_at - self.started_at).total_seconds()
```

#### テスト要件

- [ ] バッチ処理が正常に実行されること
- [ ] 変更検知が動作すること
- [ ] 当日分の更新が動作すること
- [ ] 欠落している日次要約が作成されること
- [ ] グレースフルシャットダウンが動作すること
- [ ] エラー発生時も処理が継続すること

---

### 4. NyaoBotへの統合

#### main.pyの更新

```python
class NyaoBot:
    def __init__(self, ...):
        # 既存の初期化...

        # バッチ処理の初期化
        self._batch_processor = BatchProcessor(
            summarizer=self._summarizer,
            working_memory=self._working_memory,
            short_term=self._short_term,
            slack_client=self._slack_connection,
            interval_seconds=settings.bot.batch.interval_seconds,
        )

    async def start(self) -> None:
        """アプリケーションを起動する"""
        # データベースの初期化
        await self._db_manager.init_db()

        # Slack接続の開始
        await self._slack_connection.start()

        # バッチ処理の開始
        await self._batch_processor.start()

        # クリーンアップループの開始
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """アプリケーションを停止する"""
        # バッチ処理の停止
        await self._batch_processor.stop()

        # 既存の停止処理...
```

#### 設定

```python
# config/settings.py に追加

class BatchSettings(BaseModel):
    """バッチ処理設定"""

    interval_seconds: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="バッチ処理の実行間隔（秒）",
    )
    lookback_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="過去の日次要約をチェックする日数",
    )
    long_term_update_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="長期記憶の更新間隔（時間）",
    )


class BotSettings(BaseModel):
    # 既存の設定...
    batch: BatchSettings = Field(default_factory=BatchSettings)
```

---

## ディレクトリ構成

```
nyao/
├── memory/
│   ├── __init__.py
│   ├── models.py              # データモデル
│   ├── database.py            # DatabaseManager
│   ├── working_memory.py      # WorkingMemoryService
│   ├── short_term.py          # ShortTermMemoryService
│   ├── long_term.py           # LongTermMemoryService
│   ├── context_builder.py     # MemoryContextBuilder
│   ├── summarizer.py          # MemorySummarizer
│   └── batch_processor.py     # BatchProcessor
├── integrations/
│   └── llm/
│       └── prompts.py         # 要約用プロンプト追加
├── config/
│   └── settings.py            # BatchSettings追加
└── main.py                    # BatchProcessor統合
```

---

## 実装タスク

### Day 1-2: MemorySummarizerの実装

- [ ] `memory/summarizer.py` の作成
- [ ] 要約用プロンプトテンプレートの追加
- [ ] `summarize_thread()` の実装
- [ ] `summarize_channel_daily()` の実装
- [ ] `update_workspace_memory()` の実装
- [ ] `update_channel_long_term()` の実装
- [ ] `update_user_long_term()` の実装
- [ ] テストの作成・実行

### Day 3: BatchProcessorの実装

- [ ] `memory/batch_processor.py` の作成
- [ ] `BatchSettings` の追加
- [ ] `start()` / `stop()` の実装
- [ ] `run_once()` の実装
- [ ] `_process_channel()` の実装
- [ ] 変更検知ロジックの実装
- [ ] テストの作成・実行

### Day 4: NyaoBotへの統合

- [ ] `main.py` の更新
- [ ] バッチ処理の起動・停止
- [ ] グレースフルシャットダウン対応
- [ ] 統合テストの実行

---

## テスト戦略

### ユニットテスト

```python
# tests/memory/test_summarizer.py

@pytest.mark.asyncio
async def test_summarize_thread(mock_agent, memory_services):
    """スレッド要約が正しく生成されること"""
    summarizer = MemorySummarizer(mock_agent, **memory_services)
    summary = await summarizer.summarize_thread("C123", "1234567890.123456")
    assert summary.title is not None
    assert summary.summary is not None


@pytest.mark.asyncio
async def test_summarize_channel_daily(mock_agent, memory_services):
    """チャンネル日次要約が正しく生成されること"""


# tests/memory/test_batch_processor.py

@pytest.mark.asyncio
async def test_batch_processor_start_stop():
    """バッチ処理の開始と停止"""
    processor = BatchProcessor(...)
    await processor.start()
    assert processor._running
    await processor.stop()
    assert not processor._running


@pytest.mark.asyncio
async def test_run_once():
    """バッチ処理の1回実行"""


@pytest.mark.asyncio
async def test_process_channel_with_changes():
    """変更があるチャンネルの処理"""


@pytest.mark.asyncio
async def test_process_channel_without_changes():
    """変更がないチャンネルの処理（スキップ）"""


@pytest.mark.asyncio
async def test_error_handling():
    """エラー発生時の処理継続"""
```

### モック戦略

```python
@pytest.fixture
def mock_agent(mocker):
    """NyaoAgentのモック"""
    agent = mocker.MagicMock(spec=NyaoAgent)
    agent.call_llm_with_structured_output = AsyncMock(
        return_value=ThreadSummary(...)
    )
    return agent
```

---

## エラーハンドリング

### リトライ戦略

- LLM API呼び出しは既存のリトライ機能を使用
- チャンネル処理でエラーが発生した場合、そのチャンネルをスキップして次のチャンネルを処理
- バッチ処理全体でエラーが発生した場合、次の実行まで待機

### ログ出力

```python
async def _process_channel(self, channel_id: str) -> ChannelBatchResult:
    logger.info("Processing channel", channel_id=channel_id)
    try:
        # 処理...
        logger.info(
            "Channel processed",
            channel_id=channel_id,
            today_updated=result.today_summary_updated,
            missing_created=result.missing_summaries_created,
        )
        return result
    except Exception as e:
        logger.error(
            "Failed to process channel",
            channel_id=channel_id,
            error=str(e),
        )
        return ChannelBatchResult(
            channel_id=channel_id,
            today_summary_updated=False,
            missing_summaries_created=0,
            thread_summaries_updated=0,
            errors=[str(e)],
        )
```

---

## 完了条件

- [ ] MemorySummarizerが実装されていること
  - [ ] スレッド要約生成が動作すること
  - [ ] チャンネル日次要約生成が動作すること
  - [ ] 長期記憶更新が動作すること
- [ ] BatchProcessorが実装されていること
  - [ ] 定期実行が動作すること
  - [ ] 変更検知が動作すること
  - [ ] 欠落要約の作成が動作すること
  - [ ] グレースフルシャットダウンが動作すること
- [ ] NyaoBotに統合されていること
- [ ] 全テストがパスすること
- [ ] ruff、tyによるチェックがパスすること
