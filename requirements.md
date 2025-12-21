# Slackボット要求仕様書

## 1. プロジェクト概要

### 1.1 プロジェクト名
Nyao - 反応してくれるSlackチャットボット

### 1.2 目的
Slackワークスペースにおいて、反応がないコメントに対して友達のように反応することで、孤独感を軽減し、コミュニケーションを活性化させるチャットボットを開発する。

### 1.3 コンセプト
- **友達のような存在**: お手伝いボットではなく、人間らしい振る舞いをする仲間
- **適切なタイミング**: 即座ではなく、人間が反応するような自然なタイミングで応答
- **コンテキスト理解**: 会話の流れや履歴を理解した上での応答

### 1.4 対象ワークスペース
- 規模: 約10人程度の小規模ワークスペース
- 環境: 自宅Kubernetesクラスタ上で運用

---

## 2. 機能要件

### 2.1 コア機能（MVP Phase 1）

#### 2.1.1 基本的なメッセージ応答
- **FR-001**: 指定されたチャンネルのメッセージを監視する
- **FR-002**: メッセージ投稿後、一定時間（例: 30秒〜2分）経過しても他のユーザーから反応がない場合、応答を検討する
- **FR-003**: LLMを使用して、応答すべきかどうかを判断する
  - 応答が必要そうなコメント（質問、共有、感想など）を識別
  - 応答不要なコメント（通知、自動投稿など）は無視
- **FR-004**: 人間らしい自然な応答を生成して投稿する

#### 2.1.2 チャンネル・スレッド対応
- **FR-005**: 複数の指定チャンネルで同時に動作する
- **FR-006**: スレッド内のコンテキストを理解して応答する
- **FR-007**: チャンネルごとに独立したコンテキストを管理する

#### 2.1.3 基本設定
- **FR-008**: 環境変数またはConfigMapで以下を設定可能
  - 監視対象チャンネルのリスト
  - 応答判定の待機時間
  - 使用するLLMモデル
  - ボットのペルソナ設定

### 2.2 拡張機能（Phase 2以降）

#### 2.2.1 会話履歴の記憶（階層的記憶管理システム）
- **FR-101**: 3層の階層的記憶管理システムを実装
  - ワーキングメモリ: 現在進行中の会話（30分〜1時間、最大50件）
  - 短期記憶: 最近の会話要約（過去1〜7日間）
  - 長期記憶: 高度に圧縮された本質的情報（永続的）
- **FR-102**: 過去の会話履歴を参照して、コンテキストに応じた応答を生成
- **FR-103**: LLMのコンテキストウィンドウを効率的に使用するため、記憶を自動的に要約・圧縮
- **FR-104**: チャンネル・スレッドごとの記憶を独立して管理
- **FR-105**: ユーザーごとの特性や好みを長期記憶に保存（プライバシー配慮）

#### 2.2.2 リッチコンテンツ理解
- **FR-201**: 投稿されたURLの内容を取得・要約して応答に反映
- **FR-202**: 投稿された画像を解析して内容を理解
- **FR-203**: 添付ファイル（PDF、ドキュメント等）の内容理解

#### 2.2.3 即座の応答判定
- **FR-301**: 緊急性の高いメッセージ（@メンション、質問など）を検出
- **FR-302**: 即座に応答すべきと判断した場合は待機時間をスキップ

#### 2.2.4 LLM切り替え機能
- **FR-401**: 実行時に使用するLLMモデルを切り替え可能
- **FR-402**: LiteLLMを使用して複数のLLMプロバイダーに対応
  - OpenAI (GPT-4, GPT-3.5等)
  - Anthropic (Claude)
  - ローカルLLM (Ollama等)
  - その他LiteLLMが対応するプロバイダー

#### 2.2.5 管理・制御機能
- **FR-501**: 特定のコマンドでボットの動作を制御
  - 一時停止/再開
  - 応答モードの変更
  - 統計情報の表示
- **FR-502**: 管理者による手動介入機能

---

## 3. 非機能要件

### 3.1 パフォーマンス
- **NFR-001**: メッセージ受信から応答判定まで10秒以内
- **NFR-002**: 同時に複数チャンネル（最大10チャンネル）を監視可能
- **NFR-003**: LLM APIの応答待機時に他のメッセージ処理がブロックされない（非同期処理）
- **NFR-004**: 記憶管理の要約処理がメッセージ応答をブロックしない
- **NFR-005**: コンテキスト構築時間は3秒以内

### 3.2 信頼性
- **NFR-006**: Slack APIの一時的な障害時に自動リトライ
- **NFR-007**: LLM APIエラー時のフォールバック処理
- **NFR-008**: Kubernetes Pod再起動時の状態復旧
- **NFR-009**: 記憶管理の要約処理失敗時のエラーハンドリング

### 3.3 セキュリティ
- **NFR-010**: Slack APIトークンは環境変数またはKubernetes Secretで管理
- **NFR-011**: LLM APIキーは環境変数またはKubernetes Secretで管理
- **NFR-012**: 会話履歴のデータは暗号化して保存（Phase 2以降）
- **NFR-013**: ユーザーのプライバシーに配慮したデータ管理
- **NFR-014**: 機密情報（クレジットカード番号、電話番号等）の自動マスキング
- **NFR-015**: ユーザーによる記憶の削除・確認機能

### 3.4 保守性
- **NFR-016**: ログ出力は構造化ログ（JSON形式）
- **NFR-017**: メトリクス収集（Prometheus形式）の実装
- **NFR-018**: コードの品質はruffでチェック
- **NFR-019**: 依存関係管理はuvで統一
- **NFR-020**: 記憶管理システムのメトリクス収集（記憶層ごとのサイズ、要約回数等）

### 3.5 スケーラビリティ
- **NFR-021**: 将来的に複数インスタンスでの動作を考慮した設計
- **NFR-022**: データベース接続プールの適切な管理
- **NFR-023**: 記憶管理の要約・統合処理の並列化対応

---

## 4. 技術仕様

### 4.1 技術スタック

#### 4.1.1 開発環境
- **言語**: Python 3.12+
- **パッケージ管理**: uv
- **Linter/Formatter**: [ruff](https://github.com/astral-sh/ruff)
- **型チェック**: [ty](https://github.com/astral-sh/ty)

#### 4.1.2 主要ライブラリ
- **Slack連携**: `slack-sdk` または `slack-bolt`
- **LLM連携**: `litellm`
- **非同期処理**: `asyncio` + `aiohttp`
- **データベース**: 
  - Phase 1: SQLite（ローカル開発・MVP）
  - Phase 2: PostgreSQL（本番環境）
- **ORマッパー**: SQLModel（SQLAlchemy 2.0 + Pydantic統合）
- **ロギング**: `structlog`

#### 4.1.3 インフラストラクチャ
- **コンテナ化**: Docker
- **オーケストレーション**: Kubernetes
- **監視**: Prometheus + Grafana（推奨）

### 4.2 システムアーキテクチャ

```
┌─────────────────┐
│  Slack API      │
└────────┬────────┘
         │
         │ WebSocket/Events API
         │
┌────────▼────────┐
│  Slack Bot      │
│  (Python App)   │
│                 │
│  - Event Handler│
│  - Response     │
│    Generator    │
│  - Memory Mgr   │
└────────┬────────┘
         │
         ├─────────────┬──────────────┐
         │             │              │
┌────────▼────────┐ ┌──▼──────────┐ │
│  LiteLLM        │ │  Database   │ │
│  (LLM Gateway)  │ │  (SQLite/   │ │
│                 │ │   PostgreSQL)│ │
│  - OpenAI       │ │             │ │
│  - Anthropic    │ │  階層的記憶: │ │
│  - Local LLM    │ │  - ワーキング│ │
└─────────────────┘ │  - 短期記憶  │ │
                    │  - 長期記憶  │ │
                    └──────────────┘ │
                                     │
                    ┌────────────────▼┐
                    │ Memory Manager  │
                    │                 │
                    │ - 要約生成      │
                    │ - 統合処理      │
                    │ - 定期メンテナンス│
                    └─────────────────┘
```

### 4.3 データモデル（Phase 2以降）

SQLModelを使用した型安全なモデル定義。Pydanticのバリデーション機能を活用。

#### 4.3.1 ワーキングメモリ
```python
from sqlmodel import SQLModel, Field, JSON
from datetime import datetime
from typing import Optional

class WorkingMemoryMessage(SQLModel, table=True):
    __tablename__ = "working_memory"
    
    id: str = Field(primary_key=True)  # Slack message ID
    channel_id: str = Field(index=True)
    thread_ts: Optional[str] = Field(default=None, index=True)
    user_id: str = Field(index=True)
    user_name: str
    text: str
    timestamp: datetime = Field(index=True)
    attachments: list[dict] = Field(default_factory=list, sa_type=JSON)
    urls: list[str] = Field(default_factory=list, sa_type=JSON)
    reactions: list[dict] = Field(default_factory=list, sa_type=JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

#### 4.3.2 短期記憶（スレッド要約）
```python
from datetime import date

class ThreadSummary(SQLModel, table=True):
    __tablename__ = "thread_summaries"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True)
    channel_id: str = Field(index=True)
    started_at: datetime
    last_activity: datetime = Field(index=True)
    participants: list[str] = Field(sa_type=JSON)
    message_count: int
    summary: str  # 200-300 tokens
    key_points: list[str] = Field(sa_type=JSON)
    sentiment: str
    topics: list[str] = Field(sa_type=JSON)
    is_resolved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

#### 4.3.3 短期記憶（チャンネル日次要約）
```python
class ChannelDailySummary(SQLModel, table=True):
    __tablename__ = "channel_daily_summaries"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    channel_id: str = Field(index=True)
    date: date = Field(index=True)
    message_count: int
    active_users: list[str] = Field(sa_type=JSON)
    summary: str  # 300-500 tokens
    important_threads: list[str] = Field(sa_type=JSON)
    topics: list[str] = Field(sa_type=JSON)
    mood: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

#### 4.3.4 長期記憶（チャンネル特性）
```python
class ChannelLongTermMemory(SQLModel, table=True):
    __tablename__ = "channel_long_term_memory"
    
    channel_id: str = Field(primary_key=True)
    channel_name: str
    purpose: str
    typical_topics: list[str] = Field(sa_type=JSON)
    communication_style: str
    activity_pattern: str
    historical_summary: str  # 500-1000 tokens
    important_events: list[dict] = Field(sa_type=JSON)
    recurring_themes: list[str] = Field(sa_type=JSON)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    total_messages_processed: int = Field(default=0)
```

#### 4.3.5 長期記憶（ユーザー特性）
```python
class UserLongTermMemory(SQLModel, table=True):
    __tablename__ = "user_long_term_memory"
    
    user_id: str = Field(primary_key=True)
    user_name: str
    interests: list[str] = Field(sa_type=JSON)
    expertise: list[str] = Field(sa_type=JSON)
    communication_preference: str
    timezone: str
    frequent_collaborators: list[str] = Field(sa_type=JSON)
    role_in_team: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)
```

#### 4.3.6 長期記憶（知識エントリ）
```python
class KnowledgeEntry(SQLModel, table=True):
    __tablename__ = "knowledge_entries"
    
    id: str = Field(primary_key=True)
    category: str
    title: str
    content: str  # 100-200 tokens
    source_channels: list[str] = Field(sa_type=JSON)
    mentioned_users: list[str] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    relevance_score: float = Field(default=1.0, index=True)
    last_accessed: Optional[datetime] = None
```

### 4.4 環境変数

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...  # Socket Modeの場合
SLACK_CHANNEL_IDS=C123456,C789012

# LLM
LITELLM_MODEL=gpt-4
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Bot Configuration
BOT_RESPONSE_DELAY=60  # 秒
BOT_PERSONA="友達のようなカジュアルな口調"

# Database
DATABASE_URL=sqlite:///data/bot.db  # Phase 1
# DATABASE_URL=postgresql://user:pass@localhost/botdb  # Phase 2

# Logging
LOG_LEVEL=INFO
```

---

## 5. MVP定義とフェーズ計画

### Phase 1: MVP（最小実行可能プロダクト）

**目標**: 基本的な「反応してくれるボット」を実現

**実装機能**:
- FR-001 ~ FR-008（基本的なメッセージ応答、チャンネル・スレッド対応）
- シンプルな応答判定ロジック（キーワードベース + LLM）
- 1つのLLMモデルに固定（OpenAI GPT-4など）
- 基本的なワーキングメモリ（インメモリ、永続化なし）
- シンプルな長期記憶（設定ファイルベース）
- Docker + Kubernetes環境での動作

**成功基準**:
- 指定チャンネルで反応がないメッセージに対して30%以上応答
- 応答の自然さについてユーザーから肯定的なフィードバック
- 24時間以上の安定稼働

**期間**: 2〜3週間

### Phase 2: 会話履歴とリッチコンテンツ対応

**目標**: より賢く、コンテキストを理解するボット

**実装機能**:
- FR-101 ~ FR-105（階層的記憶管理システム）
- FR-201 ~ FR-203（URL・画像理解）
- PostgreSQLへの移行
- ワーキングメモリ、短期記憶、長期記憶の完全実装
- 自動要約・統合処理
- 過去の会話を参照した応答生成

**成功基準**:
- 過去の会話を踏まえた応答が50%以上
- URLや画像に対する適切な応答
- 記憶管理システムが安定稼働（要約処理が正常に動作）
- コンテキストウィンドウの効率的な使用（8000トークン以内）

**期間**: 3〜4週間

### Phase 3: 高度な応答制御

**目標**: より人間らしく、柔軟な動作

**実装機能**:
- FR-301 ~ FR-302（即座の応答判定）
- FR-401 ~ FR-402（LLM切り替え）
- FR-501 ~ FR-502（管理・制御機能）

**成功基準**:
- 緊急メッセージへの即座応答率90%以上
- LLMの切り替えが管理画面から実行可能

**期間**: 2〜3週間

### Phase 4: 最適化と拡張

**目標**: 本番運用レベルの品質

**実装機能**:
- パフォーマンスチューニング
- 詳細なメトリクス収集
- A/Bテスト機能
- マルチインスタンス対応

**期間**: 継続的改善

---

## 6. 制約事項と考慮事項

### 6.1 技術的制約
- **TC-001**: Slack API のレート制限に準拠する必要がある
- **TC-002**: LLM APIのコスト管理が必要（特にGPT-4使用時）
- **TC-003**: Kubernetes環境のリソース制限内で動作する必要がある

### 6.2 運用上の考慮事項
- **OC-001**: ボットの応答頻度が高すぎるとユーザーに煩わしさを与える可能性
- **OC-002**: 不適切な応答をした場合の手動介入の仕組みが必要
- **OC-003**: ユーザーのプライバシーに配慮したログ管理
- **OC-004**: 記憶管理の要約処理によるLLM APIコストの管理
- **OC-005**: 長期記憶の肥大化を防ぐための定期的な見直し

### 6.3 将来の拡張可能性
- **FC-001**: 複数ワークスペース対応
- **FC-002**: カスタムペルソナの切り替え
- **FC-003**: 外部API連携（天気、ニュース等）
- **FC-004**: ユーザー別の好みの学習

---

## 7. 付録

### 7.1 参考資料
- [Slack API Documentation](https://api.slack.com/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [slack-bolt Python Documentation](https://slack.dev/bolt-python/concepts)

### 7.2 用語集
- **MVP**: Minimum Viable Product（最小実行可能プロダクト）
- **LLM**: Large Language Model（大規模言語モデル）
- **Socket Mode**: Slack APIの接続方式の一つ（WebSocket使用）

### 7.3 変更履歴
| バージョン | 日付 | 変更内容 | 作成者 |
|----------|------|---------|--------|
| 1.0 | 2024-12-21 | 初版作成 | - |

---

## 8. 承認

| 役割 | 氏名 | 承認日 | 署名 |
|-----|------|--------|------|
| プロダクトオーナー | | | |
| 開発リード | | | |

---

*このドキュメントはプロジェクトの進行に応じて更新されます*
