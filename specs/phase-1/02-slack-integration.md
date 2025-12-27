# レイヤー2a: Slack連携レイヤー（Slack Integration Layer）

## 概要

Slack APIとの連携を担当し、メッセージの受信・送信、イベント処理を行います。

## 実装優先度

**高** - 基盤レイヤーの後に実装。LLM連携と並行実装可能。

## 依存関係

- **依存先**: レイヤー1（基盤レイヤー）
  - 設定管理システム
  - ロギングシステム
  - データモデル
  - エラーハンドリング
- **依存元**: レイヤー3（ビジネスロジックレイヤー）
- **並行実装可能**: LLM連携レイヤー（レイヤー2b）と独立

## コンポーネント

### 1. Slack接続管理 (Slack Connection Manager)

#### 目的

Slack APIへの接続を確立し、Socket Modeまたはイベント APIを使用してリアルタイムイベントを受信する。

#### 機能要件

- **FR-001**: Appがinviteされたチャンネルのメッセージを監視する
- **FR-005**: Appがinviteされた複数チャンネルで同時に動作する

#### 実装方針

**Phase 1ではSocket Modeを使用**します。これにより以下の利点があります：
- 外部からのHTTPSエンドポイントが不要（開発が容易）
- WebSocketベースでリアルタイム通信
- 自宅Kubernetesクラスタでの運用に適している

#### 主要インターフェース

**SlackConnectionManagerクラス**:
- `__init__(bot_token, app_token)`: 初期化
- `start()`: Slack接続を開始
- `stop()`: Slack接続を停止
- `register_message_handler(handler)`: メッセージハンドラを登録
- `register_reaction_handler(handler)`: リアクションハンドラを登録

#### Slack APIの権限設定

Slack Appに必要な権限（OAuth Scopes）:
```
Bot Token Scopes:
- channels:history    # チャンネルメッセージの読み取り
- channels:read       # チャンネル情報の読み取り
- chat:write          # メッセージの送信
- reactions:read      # リアクションの読み取り
- users:read          # ユーザー情報の読み取り

Event Subscriptions:
- message.channels    # チャンネルメッセージイベント
- reaction_added      # リアクション追加イベント
```

#### テスト要件

- Slack APIへの接続が正常に確立できること
- 接続エラー時に適切な例外がスローされること
- 接続の開始・停止が正常に動作すること

---

### 2. イベント受信 (Event Receiver)

#### 目的

Slackからのイベント（メッセージ投稿、リアクション追加等）を受信し、内部データモデルに変換する。

#### 機能要件

- **FR-001**: Appがinviteされたチャンネルのメッセージを監視する
- **FR-006**: スレッド内のコンテキストを理解して応答する

#### 主要インターフェース

**EventReceiverクラス**:
- `__init__(client)`: 初期化
- `handle_message_event(event, say)`: メッセージイベントを処理し、SlackMessageに変換
- `handle_reaction_event(event)`: リアクションイベントを処理

#### メッセージフィルタリング

以下のメッセージは処理対象外とします：
- Bot自身が投稿したメッセージ
- システムメッセージ（チャンネル参加通知等）

#### テスト要件

- メッセージイベントが正しくSlackMessageモデルに変換されること
- Bot自身のメッセージが無視されること
- スレッドメッセージが正しく識別されること
- リアクションイベントが正しく処理されること

---

### 3. メッセージ送信 (Message Sender)

#### 目的

Slackチャンネルにメッセージを送信する。

#### 機能要件

- **FR-004**: 人間らしい自然な応答を生成して投稿する
- スレッド内での返信
- エラーハンドリングとリトライ

#### 主要インターフェース

**MessageSenderクラス**:
- `__init__(client)`: 初期化
- `send_message(channel_id, text, thread_ts)`: メッセージを送信（リトライ機能付き）
- `send_typing_indicator(channel_id)`: 入力中インジケーターを表示（将来的な実装用）

#### メッセージ送信のレート制限対応

**NFR-006**: Slack APIの一時的な障害時に自動リトライ

Slack APIのレート制限:
- Tier 3: 50+ requests per minute
- Tier 4: 100+ requests per minute

対応策:
- `@with_retry`デコレータでリトライ実装
- レート制限エラー（429）時は指定された待機時間後にリトライ
- 最大3回までリトライ

#### テスト要件

- メッセージが正常に送信されること
- スレッド返信が正しく動作すること
- リトライ機能が動作すること
- レート制限エラーが適切に処理されること

---

### 4. スレッド履歴取得 (Thread History Fetcher)

#### 目的

スレッド内の過去のメッセージを取得し、コンテキスト理解のための情報を提供する。

#### 機能要件

- **FR-006**: スレッド内のコンテキストを理解して応答する

#### 主要インターフェース

**ThreadHistoryFetcherクラス**:
- `__init__(client)`: 初期化
- `fetch_thread_messages(channel_id, thread_ts, limit)`: スレッド内のメッセージを取得し、SlackMessageリストとして返す

#### テスト要件

- スレッド履歴が正しく取得されること
- メッセージが時系列順に並んでいること
- Bot自身のメッセージが除外されること
- エラー時に適切な例外がスローされること

---

### 5. チャンネル履歴取得 (Channel History Fetcher)

#### 目的

チャンネル内の過去のメッセージ（スレッドに属さないもの）を取得し、コンテキスト理解のための情報を提供する。

#### 機能要件

- **FR-006a**: スレッドに属さないチャンネル内の過去メッセージも参照してコンテキストを理解する

#### 主要インターフェース

**ChannelHistoryFetcherクラス**:
- `__init__(client)`: 初期化
- `fetch_channel_messages(channel_id, limit, oldest)`: チャンネル内のメッセージを取得し、SlackMessageリストとして返す
  - スレッドの親メッセージは含むが、スレッド内の返信は含まない
  - `oldest`パラメータで取得開始時刻を指定可能

#### テスト要件

- チャンネル履歴が正しく取得されること
- メッセージが時系列順に並んでいること
- Bot自身のメッセージが除外されること
- スレッド返信が除外されること
- エラー時に適切な例外がスローされること

---

## ディレクトリ構成

```
nyao/
└── integrations/
    └── slack/
        ├── __init__.py
        ├── connection.py       # SlackConnectionManager
        ├── event_receiver.py   # EventReceiver
        ├── message_sender.py   # MessageSender
        ├── thread_fetcher.py   # ThreadHistoryFetcher
        └── channel_fetcher.py  # ChannelHistoryFetcher
```

## 実装タスク

### タスク1: Slack接続管理

- [x] `integrations/slack/connection.py`の実装
- [x] Socket Mode接続の確立
- [x] イベントハンドラの登録機能
- [x] 接続の開始・停止
- [x] テストコードの作成

### タスク2: イベント受信

- [x] `integrations/slack/event_receiver.py`の実装
- [x] メッセージイベントの処理
- [x] リアクションイベントの処理
- [x] ユーザー情報取得（キャッシュ機能含む）
- [x] テストコードの作成

### タスク3: メッセージ送信

- [x] `integrations/slack/message_sender.py`の実装
- [x] メッセージ送信機能
- [x] スレッド返信機能
- [x] リトライ機能
- [x] レート制限対応
- [x] テストコードの作成

### タスク4: スレッド履歴取得

- [x] `integrations/slack/thread_fetcher.py`の実装
- [x] スレッドメッセージ取得機能
- [x] ユーザー情報取得（キャッシュ機能含む）
- [x] テストコードの作成

### タスク5: チャンネル履歴取得

- [x] `integrations/slack/channel_fetcher.py`の実装
- [x] チャンネルメッセージ取得機能
- [x] スレッド返信の除外
- [x] テストコードの作成

## テスト戦略

### ユニットテスト

**イベント受信** (`tests/integrations/slack/test_event_receiver.py`):
- メッセージイベントが正しく処理されること
- Bot自身のメッセージが無視されること
- スレッドメッセージが正しく識別されること

**メッセージ送信** (`tests/integrations/slack/test_message_sender.py`):
- メッセージが正常に送信されること
- エラー時にリトライが動作すること
- レート制限エラーが適切に処理されること

**スレッド履歴取得** (`tests/integrations/slack/test_thread_fetcher.py`):
- スレッドメッセージが正しく取得されること

**チャンネル履歴取得** (`tests/integrations/slack/test_channel_fetcher.py`):
- チャンネルメッセージが正しく取得されること
- スレッド返信が除外されること

### モックの使用

Slack APIへの実際の通信は行わず、AsyncMockを使用してテストします。

## 依存パッケージ

```toml
[tool.uv.dependencies]
slack-bolt = "^1.18"
slack-sdk = "^3.27"
```

## 完了条件

- [x] Slack APIへの接続が確立できること
- [x] メッセージイベントが受信・処理できること
- [x] メッセージが送信できること
- [x] スレッド返信が動作すること
- [x] スレッド履歴が取得できること
- [x] チャンネル履歴が取得できること
- [x] リトライ機能が動作すること
- [x] すべてのユニットテストがパスすること
- [x] ruffによるコード品質チェックがパスすること
- [x] tyによる型チェックがパスすること

**完了日**: 2025-12-25

## 参考資料

- [Slack Bolt for Python](https://slack.dev/bolt-python/concepts)
- [Slack API Documentation](https://api.slack.com/)
- [Socket Mode](https://api.slack.com/apis/connections/socket)
