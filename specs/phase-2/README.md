# Phase 2: 階層的記憶管理とスマート応答

## 概要

Phase 2では、階層的記憶管理システムの実装と、スマート応答判定機能を追加します。
また、strands-agentsからLiteLLM直接使用への移行を行い、将来のtool call対応に備えたAgent loopを自前で実装します。

## 目標

- 階層的記憶管理システムにより、コンテキストを理解した応答を生成
- スマート応答判定（再判定、返信先判定、リクエストごとのjitter）
- LiteLLM直接使用への移行（strands-agents依存の削除）

## 実装範囲

### 含まれる機能

#### 階層的記憶管理システム（FR-101 ~ FR-105）
- **FR-101**: 3層の階層的記憶管理システムを実装
  - ワーキングメモリ: 過去x日分のメッセージ（LiteLLMメッセージ形式）
  - 短期記憶: スレッド要約、チャンネル日次要約
  - 長期記憶: ワークスペース要約、チャンネル特性、ユーザー特性
- **FR-102**: 過去の会話履歴を参照して、コンテキストに応じた応答を生成
- **FR-103**: LLMのコンテキストウィンドウを効率的に使用するため、記憶を自動的に要約・圧縮
- **FR-104**: チャンネル・スレッドごとの記憶を独立して管理
- **FR-105**: ユーザーごとの特性や好みを長期記憶に保存

#### スマート応答判定（FR-601 ~ FR-603）
- **FR-601**: 返答しないと判定したメッセージに対して、一定時間経過後に再判定
  - 条件: 固定時間経過 + 新しいメッセージがない場合
  - 最大再判定回数を設定可能
- **FR-602**: 返信先（スレッド/チャンネル）を判定
  - 個人的な話題・既存スレッドの話題 → スレッドに返信
  - みんなに見てもらいたい内容 → チャンネルに直接投稿
- **FR-603**: レスポンス遅延時間をリクエストごとにjitter適用

### 技術的変更

- strands-agentsからLiteLLM直接使用への移行

### Phase 3以降で実装

- Agent loop（tool call対応）

### Phase 2で含まれない機能（Phase 3以降）

- URL・画像などのリッチコンテンツ理解（FR-201 ~ FR-203）
- 即座の応答判定（FR-301 ~ FR-302）
- LLMの動的切り替え（FR-401 ~ FR-402）
- 管理・制御コマンド（FR-501 ~ FR-502）
- PostgreSQLへの移行

---

## アーキテクチャ

### 全体構成

```
┌─────────────────┐
│  Slack API      │
└────────┬────────┘
         │
         │ Socket Mode / Events API
         │
┌────────▼────────────────────────┐
│  Slack Bot (Python App)         │
│                                 │
│  ┌─────────────────────────┐   │
│  │ Event Handler           │   │
│  │ - メッセージ受信         │   │
│  │ - 反応待機（jitter適用）  │   │
│  │ - 再判定スケジューラー    │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ Response Judge          │   │
│  │ - 応答判定               │   │
│  │ - 返信先判定             │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ Memory Context Builder  │   │
│  │ - 階層的記憶の組み立て   │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ Response Generator      │   │
│  │ - 応答生成               │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ Memory Manager          │   │
│  │ - ワーキングメモリ       │   │
│  │ - 短期記憶               │   │
│  │ - 長期記憶               │   │
│  │ - 要約生成               │   │
│  └─────────────────────────┘   │
└─────────────┬───────────────────┘
              │
    ┌─────────▼──────────────┐
    │  LiteLLM (直接使用)    │
    │                        │
    │  - OpenAI              │
    │  - Anthropic           │
    │  - Local LLM           │
    └────────────────────────┘
              │
    ┌─────────▼──────────────┐
    │  SQLite Database       │
    │                        │
    │  階層的記憶:            │
    │  - working_memory      │
    │  - thread_summaries    │
    │  - channel_daily_...   │
    │  - workspace_memory    │
    │  - channel_long_term.. │
    │  - user_long_term_...  │
    └────────────────────────┘
```

### LLM連携（LiteLLM直接使用）

strands-agentsを削除し、LiteLLMの`acompletion`を直接使用します。

```python
class NyaoAgent:
    """LiteLLMを直接使用するエージェント基盤"""

    async def call_llm(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """LiteLLM acompletion を呼び出し"""

    async def call_llm_with_structured_output(
        self,
        messages: list[dict],
        output_model: type[T],
    ) -> T:
        """JSON出力を要求し、Pydanticモデルにパース"""
```

※ tool call対応（Agent loop）はPhase 3以降で実装

### 階層的記憶管理システム

#### ワーキングメモリ（working_memory テーブル）
- 過去x日分のメッセージを保持
- LiteLLMのメッセージ形式に近い形で保存
  - role: "user" または "assistant"
  - content: テキスト内容
  - attachments: base64エンコードされたファイル（画像等）
- Slack固有の情報（channel_id, thread_ts, user_id等）も別途保持

#### 短期記憶
- **thread_summaries**: スレッド要約（タイトル、要約、トピック）
- **channel_daily_summaries**: チャンネル日次要約

#### 長期記憶
- **workspace_memory**: ワークスペース全体の要約（シングルトン）
- **channel_long_term_memory**: チャンネル特性
- **user_long_term_memory**: ユーザー特性

---

## データモデル（SQLModel）

### ワーキングメモリ

```python
class WorkingMemoryMessage(SQLModel, table=True):
    __tablename__ = "working_memory"

    id: str = Field(primary_key=True)  # Slack message ts
    channel_id: str = Field(index=True)
    thread_ts: str | None = Field(default=None, index=True)
    user_id: str = Field(index=True)
    user_name: str

    # LiteLLMメッセージ形式
    role: str  # "user" or "assistant"
    content: str = Field(sa_column=Column(Text))
    attachments: list[dict] = Field(default_factory=list, sa_type=JSON)  # base64

    timestamp: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### スレッド要約

```python
class ThreadSummary(SQLModel, table=True):
    __tablename__ = "thread_summaries"

    id: int | None = Field(default=None, primary_key=True)
    thread_ts: str = Field(index=True)
    channel_id: str = Field(index=True)
    title: str  # スレッドのタイトル（LLM生成）
    summary: str = Field(sa_column=Column(Text))
    key_topics: list[str] = Field(sa_type=JSON)
    participants: list[str] = Field(sa_type=JSON)
    message_count: int
    started_at: datetime
    last_activity: datetime = Field(index=True)
    is_resolved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### チャンネル日次要約

```python
class ChannelDailySummary(SQLModel, table=True):
    __tablename__ = "channel_daily_summaries"

    id: int | None = Field(default=None, primary_key=True)
    channel_id: str = Field(index=True)
    date: date = Field(index=True)
    message_count: int
    active_users: list[str] = Field(sa_type=JSON)
    summary: str = Field(sa_column=Column(Text))
    important_threads: list[str] = Field(sa_type=JSON)
    topics: list[str] = Field(sa_type=JSON)
    mood: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### ワークスペース記憶

```python
class WorkspaceMemory(SQLModel, table=True):
    __tablename__ = "workspace_memory"

    id: int = Field(default=1, primary_key=True)  # シングルトン
    summary: str = Field(sa_column=Column(Text))
    important_events: list[dict] = Field(sa_type=JSON)
    recurring_topics: list[str] = Field(sa_type=JSON)
    team_culture: str = Field(sa_column=Column(Text))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### チャンネル長期記憶

```python
class ChannelLongTermMemory(SQLModel, table=True):
    __tablename__ = "channel_long_term_memory"

    channel_id: str = Field(primary_key=True)
    channel_name: str
    purpose: str
    typical_topics: list[str] = Field(sa_type=JSON)
    historical_summary: str = Field(sa_column=Column(Text))
    important_events: list[dict] = Field(sa_type=JSON)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### ユーザー長期記憶

```python
class UserLongTermMemory(SQLModel, table=True):
    __tablename__ = "user_long_term_memory"

    user_id: str = Field(primary_key=True)
    user_name: str
    interests: list[str] = Field(sa_type=JSON)
    expertise: list[str] = Field(sa_type=JSON)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## プロンプトコンテキストの要件

応答生成時のコンテキストには、以下の階層的記憶を含める：

1. **長期記憶**
   - ワークスペース全体の要約・特性
   - チャンネルの要約・特性

2. **短期記憶**
   - チャンネル日次要約（過去x日分）
   - スレッド要約・タイトル

3. **ワーキングメモリ**
   - 直近のメッセージ（生データ）

具体的なプロンプト形式は実装時に最適な形を決定します。

---

## 実装計画

### Phase 2.1: LiteLLM直接使用への移行

1. 新しい `NyaoAgent` クラスの実装（LiteLLM acompletion使用）
2. `call_llm_with_structured_output` の実装（JSON出力→Pydanticパース）
3. `ResponseJudgeAgent` の更新
4. `ResponseGeneratorAgent` の更新
5. `pyproject.toml` から strands-agents を削除

### Phase 2.2: 遅延・再判定機能

1. `ResponseDelayController` のjitter毎回計算対応
2. `RejudgeTracker` の実装
3. `NyaoBot` への再判定ループ統合
4. 設定ファイル更新

### Phase 2.3: 返信先判定

1. `ResponseDecision` の拡張（ReplyTarget enum追加）
2. プロンプトの更新
3. `NyaoBot._check_and_respond` の更新

### Phase 2.4: 階層的記憶管理

1. データモデル定義（SQLModel）
2. DB初期化
3. 各記憶層の実装
4. `MemorySummarizer` の実装
5. `MemoryContextBuilder` の実装
6. プロンプト構築の更新
7. 日次要約バッチ処理の実装
   - 10分間隔で実行
   - チャンネルごとに変更検知（最終更新時刻を追跡）
   - 当日分: 変更があれば更新
   - 過去x日分: 存在しなければ作成

---

## 成功基準

- strands-agents依存が完全に削除されている
- リクエストごとにjitterが適用されている
- 再判定機能が動作している
- 返信先判定が正しく動作している
- 階層的記憶管理が動作し、プロンプトに反映されている
- 日次要約バッチが正常に実行されている
- 過去の会話を踏まえた応答が50%以上
- コンテキストウィンドウの効率的な使用（8000トークン以内）
- 既存のテストがすべてパスしている

---

## ドキュメント構成

- [README.md](./README.md) - 本ドキュメント（Phase 2全体像）
- [implementation-plan.md](./implementation-plan.md) - 実装計画（Week 1-4）
- [01-litellm-migration.md](./01-litellm-migration.md) - LiteLLM直接使用への移行設計
- [02-smart-response.md](./02-smart-response.md) - スマート応答判定設計
- [03-memory-models.md](./03-memory-models.md) - 階層的記憶のデータモデル設計
- [04-memory-services.md](./04-memory-services.md) - 記憶管理サービス設計
- [05-batch-processing.md](./05-batch-processing.md) - 日次要約バッチ処理設計

## 参考資料

- [プロジェクト要求仕様書](../../requirements.md)
- [Phase 1仕様書](../phase-1/README.md)
- [LiteLLM Documentation](https://docs.litellm.ai/)
