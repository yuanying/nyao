# 階層的記憶管理 - データモデル設計

## 概要

Phase 2.4では、階層的記憶管理システムのデータモデルをSQLModelを使用して実装します。3層の記憶（ワーキングメモリ、短期記憶、長期記憶）をSQLiteデータベースに永続化します。

## 実装優先度

**高** - Phase 2.4の基盤となるデータ層

## 依存関係

### 依存先
- Phase 2.1-2.3: LiteLLM移行、スマート応答判定
- SQLModel、aiosqlite パッケージ

### 依存元
- Phase 2.4: 記憶管理サービス（04-memory-services.md）
- Phase 2.4: バッチ処理（05-batch-processing.md）

---

## データモデル

### 1. WorkingMemoryMessage - ワーキングメモリ

#### 目的

過去X日分のメッセージをLiteLLMメッセージ形式に近い形で保存します。

#### 機能要件

- **FR-101**: ワーキングメモリとして過去x日分のメッセージを保持
- **FR-104**: チャンネル・スレッドごとの記憶を独立して管理

#### スキーマ定義

```python
from datetime import datetime, UTC
from sqlmodel import Field, SQLModel, Column, Text, JSON


class WorkingMemoryMessage(SQLModel, table=True):
    """ワーキングメモリ - リアルタイムメッセージ"""

    __tablename__ = "working_memory"

    # 主キー: Slackのメッセージタイムスタンプ
    id: str = Field(primary_key=True)

    # Slack固有の情報
    channel_id: str = Field(index=True)
    thread_ts: str | None = Field(default=None, index=True)
    user_id: str = Field(index=True)
    user_name: str

    # LiteLLMメッセージ形式
    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(sa_column=Column(Text))
    attachments: list[dict] = Field(
        default_factory=list,
        sa_type=JSON,
        description="Base64エンコードされたファイル（画像等）",
    )

    # タイムスタンプ
    timestamp: datetime = Field(index=True, description="メッセージの投稿時刻")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="レコードの作成時刻",
    )
```

#### インデックス設計

- `id`: 主キー（Slack message ts）
- `channel_id`: チャンネルごとのメッセージ取得
- `thread_ts`: スレッドごとのメッセージ取得
- `user_id`: ユーザーごとのメッセージ取得
- `timestamp`: 時系列でのメッセージ取得、古いメッセージの削除

#### バリデーションルール

- `role`: "user" または "assistant" のみ許可
- `content`: 空文字列は許可（添付ファイルのみの場合）
- `timestamp`: 未来の日時は許可しない

---

### 2. ThreadSummary - スレッド要約

#### 目的

スレッド単位の要約を保存し、短期記憶として活用します。

#### 機能要件

- **FR-101**: 短期記憶としてスレッド要約を保持
- **FR-103**: 記憶を自動的に要約・圧縮

#### スキーマ定義

```python
class ThreadSummary(SQLModel, table=True):
    """スレッド要約 - 短期記憶"""

    __tablename__ = "thread_summaries"

    id: int | None = Field(default=None, primary_key=True)

    # スレッド識別
    thread_ts: str = Field(index=True)
    channel_id: str = Field(index=True)

    # 要約内容（LLM生成）
    title: str = Field(description="スレッドのタイトル")
    summary: str = Field(sa_column=Column(Text), description="スレッドの要約")
    key_topics: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="主要トピックのリスト",
    )
    participants: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="参加者のuser_idリスト",
    )

    # メタデータ
    message_count: int = Field(description="メッセージ数")
    started_at: datetime = Field(description="スレッド開始時刻")
    last_activity: datetime = Field(index=True, description="最終活動時刻")
    is_resolved: bool = Field(default=False, description="解決済みかどうか")

    # タイムスタンプ
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

#### インデックス設計

- `id`: 主キー（自動採番）
- `thread_ts`: スレッドの特定
- `channel_id`: チャンネルごとのスレッド一覧
- `last_activity`: アクティブなスレッドの取得

#### 一意制約

- `(thread_ts, channel_id)`: 同一スレッドの重複を防止

---

### 3. ChannelDailySummary - チャンネル日次要約

#### 目的

チャンネルの日次要約を保存し、短期記憶として活用します。

#### 機能要件

- **FR-101**: 短期記憶としてチャンネル日次要約を保持
- **FR-103**: 記憶を自動的に要約・圧縮

#### スキーマ定義

```python
from datetime import date


class ChannelDailySummary(SQLModel, table=True):
    """チャンネル日次要約 - 短期記憶"""

    __tablename__ = "channel_daily_summaries"

    id: int | None = Field(default=None, primary_key=True)

    # チャンネル・日付
    channel_id: str = Field(index=True)
    date: date = Field(index=True)

    # 要約内容（LLM生成）
    summary: str = Field(sa_column=Column(Text), description="日次要約")
    topics: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="話題のリスト",
    )
    mood: str = Field(description="チャンネルの雰囲気")

    # メタデータ
    message_count: int = Field(description="メッセージ数")
    active_users: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="アクティブユーザーのuser_idリスト",
    )
    important_threads: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="重要スレッドのthread_tsリスト",
    )

    # タイムスタンプ
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

#### インデックス設計

- `id`: 主キー（自動採番）
- `channel_id`: チャンネルごとの要約取得
- `date`: 日付での要約取得

#### 一意制約

- `(channel_id, date)`: 同一チャンネル・同一日付の重複を防止

---

### 4. WorkspaceMemory - ワークスペース記憶

#### 目的

ワークスペース全体の要約と特性を保存します（シングルトン）。

#### 機能要件

- **FR-101**: 長期記憶としてワークスペース要約を保持

#### スキーマ定義

```python
class WorkspaceMemory(SQLModel, table=True):
    """ワークスペース記憶 - 長期記憶（シングルトン）"""

    __tablename__ = "workspace_memory"

    # シングルトンとして扱う（id=1のみ）
    id: int = Field(default=1, primary_key=True)

    # 要約内容（LLM生成）
    summary: str = Field(
        sa_column=Column(Text),
        description="ワークスペース全体の要約",
    )
    team_culture: str = Field(
        sa_column=Column(Text),
        description="チームの文化・雰囲気",
    )
    recurring_topics: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="繰り返し話題になるトピック",
    )
    important_events: list[dict] = Field(
        default_factory=list,
        sa_type=JSON,
        description="重要なイベント（日付、内容）",
    )

    # タイムスタンプ
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

#### 使用方法

```python
# 取得（なければ作成）
async def get_or_create_workspace_memory(session: AsyncSession) -> WorkspaceMemory:
    result = await session.get(WorkspaceMemory, 1)
    if result is None:
        result = WorkspaceMemory(
            id=1,
            summary="",
            team_culture="",
        )
        session.add(result)
        await session.commit()
    return result
```

---

### 5. ChannelLongTermMemory - チャンネル長期記憶

#### 目的

チャンネルの特性と履歴を保存します。

#### 機能要件

- **FR-101**: 長期記憶としてチャンネル特性を保持

#### スキーマ定義

```python
class ChannelLongTermMemory(SQLModel, table=True):
    """チャンネル長期記憶"""

    __tablename__ = "channel_long_term_memory"

    # チャンネルIDを主キーとして使用
    channel_id: str = Field(primary_key=True)
    channel_name: str = Field(description="チャンネル名")

    # チャンネル特性（LLM生成）
    purpose: str = Field(description="チャンネルの目的")
    typical_topics: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="よく話題になるトピック",
    )

    # 履歴情報
    historical_summary: str = Field(
        sa_column=Column(Text),
        description="過去の重要な出来事の要約",
    )
    important_events: list[dict] = Field(
        default_factory=list,
        sa_type=JSON,
        description="重要なイベント（日付、内容）",
    )

    # タイムスタンプ
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

### 6. UserLongTermMemory - ユーザー長期記憶

#### 目的

ユーザーごとの特性と好みを保存します。

#### 機能要件

- **FR-105**: ユーザーごとの特性や好みを長期記憶に保存

#### スキーマ定義

```python
class UserLongTermMemory(SQLModel, table=True):
    """ユーザー長期記憶"""

    __tablename__ = "user_long_term_memory"

    # ユーザーIDを主キーとして使用
    user_id: str = Field(primary_key=True)
    user_name: str = Field(description="ユーザー名")

    # ユーザー特性（LLM生成）
    interests: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="興味・関心のあるトピック",
    )
    expertise: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
        description="専門知識・スキル",
    )

    # タイムスタンプ
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## データベース初期化

### DatabaseManager

```python
# memory/database.py

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel


class DatabaseManager:
    """データベース管理"""

    def __init__(self, database_url: str = "sqlite+aiosqlite:///nyao.db") -> None:
        """
        データベースマネージャーを初期化する。

        Args:
            database_url: データベースURL
        """
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """
        データベースを初期化する（テーブル作成）。
        """
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """
        新しいセッションを取得する。

        Returns:
            AsyncSession: 非同期セッション
        """
        return self._session_factory()

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """
        セッションスコープを提供するコンテキストマネージャー。

        Yields:
            AsyncSession: 非同期セッション
        """
        session = await self.get_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """
        データベース接続を閉じる。
        """
        await self._engine.dispose()
```

### 設定

```python
# config/settings.py に追加

class DatabaseSettings(BaseModel):
    """データベース設定"""

    url: str = Field(
        default="sqlite+aiosqlite:///nyao.db",
        description="データベースURL",
    )
    echo: bool = Field(
        default=False,
        description="SQLログを出力するか",
    )


class Settings(BaseSettings):
    # 既存の設定...
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
```

---

## ディレクトリ構成

```
nyao/
├── memory/
│   ├── __init__.py
│   ├── models.py      # 全データモデル
│   └── database.py    # DatabaseManager
```

---

## 実装タスク

### Day 1: モデル定義

- [ ] `memory/models.py` の作成
- [ ] `WorkingMemoryMessage` の実装
- [ ] `ThreadSummary` の実装
- [ ] `ChannelDailySummary` の実装
- [ ] `WorkspaceMemory` の実装
- [ ] `ChannelLongTermMemory` の実装
- [ ] `UserLongTermMemory` の実装

### Day 2: データベース初期化

- [ ] `memory/database.py` の作成
- [ ] `DatabaseManager` の実装
- [ ] 設定への `DatabaseSettings` の追加
- [ ] 依存パッケージの追加（sqlmodel, aiosqlite）
- [ ] テストの作成・実行

---

## テスト戦略

### ユニットテスト

```python
# tests/memory/test_models.py

def test_working_memory_message_creation():
    """WorkingMemoryMessageが正しく作成されること"""
    msg = WorkingMemoryMessage(
        id="1234567890.123456",
        channel_id="C123",
        user_id="U123",
        user_name="test_user",
        role="user",
        content="Hello",
        timestamp=datetime.now(UTC),
    )
    assert msg.id == "1234567890.123456"
    assert msg.role == "user"


def test_thread_summary_creation():
    """ThreadSummaryが正しく作成されること"""


def test_channel_daily_summary_creation():
    """ChannelDailySummaryが正しく作成されること"""


# tests/memory/test_database.py

@pytest.mark.asyncio
async def test_database_initialization():
    """データベースが正しく初期化されること"""
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init_db()
    # テーブルが作成されていることを確認


@pytest.mark.asyncio
async def test_session_scope():
    """セッションスコープが正しく動作すること"""


@pytest.mark.asyncio
async def test_crud_operations():
    """CRUD操作が正しく動作すること"""
```

### インメモリデータベースを使用したテスト

```python
@pytest.fixture
async def db_manager():
    """テスト用データベースマネージャー"""
    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await manager.init_db()
    yield manager
    await manager.close()
```

---

## 依存パッケージ

```toml
[project.dependencies]
sqlmodel = ">=0.0.22"
aiosqlite = ">=0.19.0"
```

---

## 完了条件

- [ ] すべてのデータモデルが定義されていること
  - [ ] WorkingMemoryMessage
  - [ ] ThreadSummary
  - [ ] ChannelDailySummary
  - [ ] WorkspaceMemory
  - [ ] ChannelLongTermMemory
  - [ ] UserLongTermMemory
- [ ] DatabaseManagerが実装されていること
- [ ] データベースが正しく初期化されること
- [ ] CRUD操作が動作すること
- [ ] 全テストがパスすること
- [ ] ruff、tyによるチェックがパスすること
