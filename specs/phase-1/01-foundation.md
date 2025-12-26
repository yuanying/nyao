# レイヤー1: 基盤レイヤー（Foundation Layer）

## 概要

基盤レイヤーは、すべての上位レイヤーが依存する共通機能を提供します。Phase 1の最初に実装すべきコンポーネント群です。

## 実装優先度

**最優先** - すべての機能の基礎となるため、最初に実装が必要

## 依存関係

- **依存先**: なし（最下層レイヤー）
- **依存元**: すべての上位レイヤー

## コンポーネント

### 1. 設定管理システム (Config Manager)

#### 目的

環境変数や設定ファイルから設定を読み込み、アプリケーション全体で一貫した設定管理を提供する。

#### 機能要件

- **FR-008**: 環境変数またはConfigMapで以下を設定可能
  - 応答判定の待機時間
  - 使用するLLMモデル
  - ボットのペルソナ設定

#### 設定項目

**環境変数での設定（必須項目のみ）**
- `SLACK_BOT_TOKEN`: Bot User OAuth Token（必須）
- `SLACK_APP_TOKEN`: App-Level Token（必須）
- `NYAO_CONFIG_PATH`: 設定ファイルのパス（デフォルト: `config.yaml`）

**設定ファイルでの設定**

設定ファイル（YAML形式）では以下を設定可能：

```yaml
# LLM設定（strands-agents LiteLLMModel形式）
litellm:
  model_id: "openai/gpt-4o"  # 必須: プロバイダー/モデル形式
  client_args:  # オプション: LiteLLMクライアント引数
    api_key: "$OPENAI_API_KEY"  # $プレフィックスで環境変数を参照
  params:  # オプション: モデルパラメータ
    temperature: 0.7
    max_tokens: 1000

# Bot動作設定
bot:
  response_delay:  # 応答判定までの待機時間設定
    base: 60  # 基本待機時間（秒、デフォルト: 60）
    jitter: 10  # ランダムな揺らぎ（秒、デフォルト: 10）
  persona: "友達のようなカジュアルな口調で話す"  # ボットのペルソナ設定

# ログ設定
logging:
  level: "INFO"  # ログレベル（デフォルト: "INFO"）
```

#### 実装方針

- **Pydantic Settings**を使用して型安全な設定管理
- 環境変数の自動読み込みとバリデーション
- `.env`ファイルのサポート
- YAMLファイルからの設定読み込み（PyYAML使用）
- 設定値内の環境変数参照（`$VAR_NAME`形式）の展開
- 待機時間のjitter機能（`base ± random(0, jitter)`）
- 設定の不正値に対するバリデーションエラー

#### 主要インターフェース

- `get_settings()`: 設定のシングルトンインスタンスを取得
- `reload_settings()`: 設定を再読み込み（開発時のみ使用）
- `get_response_delay_with_jitter()`: jitterを適用した待機時間を取得

#### テスト要件

- 環境変数が正しく読み込まれること
- YAMLファイルから設定が正しく読み込まれること
- 設定値内の環境変数参照（`$VAR_NAME`）が正しく展開されること
- デフォルト値が正しく適用されること
- 必須項目が欠けている場合にエラーが発生すること
- 不正な値（例: チャンネルIDのフォーマット違反）が検出されること
- jitterを適用した待機時間が正しい範囲内にあること

---

### 2. ロギングシステム (Logging System)

#### 目的

構造化ログ（JSON形式）を提供し、本番環境での監視とデバッグを容易にする。

#### 機能要件

- **NFR-016**: ログ出力は構造化ログ（JSON形式）
- ログレベルの制御（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- コンテキスト情報の自動付与（タイムスタンプ、モジュール名、関数名等）
- 機密情報のマスキング（APIキー、トークン等）

#### 実装方針

- **structlog**を使用した構造化ログ
- JSON形式での出力（Kubernetes環境でのログ収集に最適）
- ログレベルは環境変数で制御可能
- 開発環境では人間が読みやすいフォーマット、本番環境ではJSON形式

#### ログフォーマット

**本番環境（JSON形式）**:
```json
{
  "timestamp": "2024-12-21T10:30:45.123Z",
  "level": "info",
  "event": "message_received",
  "channel_id": "C123456",
  "user_id": "U789012",
  "logger": "nyao.slack.handler",
  "function": "handle_message"
}
```

**開発環境（コンソール形式）**:
```
2024-12-21 10:30:45 [info] message_received channel_id=C123456 user_id=U789012
```

#### 主要インターフェース

- `setup_logging(log_level, development)`: ロギングシステムの初期化
- `get_logger(name)`: モジュールごとのロガーを取得

#### 機密情報のマスキング

以下のフィールドは自動的にマスキングされます：
- `slack_bot_token`, `slack_app_token`
- `openai_api_key`, `anthropic_api_key`
- `api_key`, `token`, `password`

例: `{"slack_bot_token": "xoxb-123..."}` → `{"slack_bot_token": "***MASKED***"}`

#### テスト要件

- ログが正しいフォーマットで出力されること
- ログレベルのフィルタリングが機能すること
- 機密情報が自動的にマスキングされること
- コンテキスト情報が正しく付与されること

---

### 3. データモデル定義 (Data Models)

#### 目的

アプリケーション全体で使用するデータモデルを定義し、型安全性を確保する。

#### Phase 1でのデータモデル

Phase 1ではデータベースを使用せず、インメモリでデータを管理します。

#### メッセージモデル (SlackMessage)

**主要フィールド**:
- `message_id`: メッセージID（ts値）
- `channel_id`: チャンネルID
- `thread_ts`: スレッドタイムスタンプ（オプション）
- `user_id`: ユーザーID
- `user_name`: ユーザー名
- `text`: メッセージ本文
- `timestamp`: 投稿日時

**メタデータ**:
- `reactions`: リアクションリスト
- `reply_count`: 返信数

#### コンテキストモデル (ConversationContext)

**主要フィールド**:
- `channel_id`: チャンネルID
- `thread_ts`: スレッドタイムスタンプ（オプション）
- `messages`: メッセージ履歴のリスト
- `last_updated`: 最終更新日時

**主要メソッド**:
- `add_message(message)`: メッセージを追加
- `get_recent_messages(limit)`: 直近のメッセージを取得

#### 応答判定結果モデル (ResponseDecision)

**主要フィールド**:
- `should_respond`: 応答すべきか（bool）
- `reason`: 判定理由（str）
- `confidence`: 確信度（0.0-1.0）
- `suggested_delay_minutes`: 提案される遅延時間（分、オプション、Phase 2以降で使用）

**設計ノート**:
Phase 2以降の拡張を見据えて、オプショナルフィールドを含む拡張可能な構造としています。

#### LLM応答モデル (LLMResponse)

**主要フィールド**:
- `content`: 生成されたテキスト
- `model`: 使用したモデル名
- `usage`: トークン使用量（dict）
- `finish_reason`: 終了理由

#### テスト要件

- 各モデルのバリデーションが機能すること
- 不正な値が拒否されること
- JSONシリアライズ・デシリアライズが正しく動作すること
- datetime型が正しくISO8601形式に変換されること

---

### 4. エラーハンドリング基盤 (Error Handling)

#### 目的

アプリケーション全体で一貫したエラーハンドリングを提供し、適切なログ出力とリトライ機能を実装する。

#### カスタム例外クラス

**基底例外**:
- `NyaoException`: Nyaoアプリケーションの基底例外

**個別例外**:
- `SlackAPIError`: Slack API関連のエラー
  - 属性: `error_code`
- `LLMAPIError`: LLM API関連のエラー
  - 属性: `model`, `status_code`
- `ConfigurationError`: 設定関連のエラー
- `ContextManagementError`: コンテキスト管理関連のエラー

#### リトライ機能

**主要関数**:
- `retry_async(func, max_retries, delay, backoff, exceptions)`: 非同期関数のリトライ実行
  - `max_retries`: 最大リトライ回数（デフォルト: 3）
  - `delay`: 初回リトライまでの待機時間（秒、デフォルト: 1.0）
  - `backoff`: リトライごとの待機時間の倍率（デフォルト: 2.0）
  - `exceptions`: リトライ対象の例外タプル

**デコレータ**:
- `@with_retry(max_retries=3, delay=1.0)`: リトライ機能を関数に適用

#### エラーハンドリングパターン

**NFR-006**: Slack APIの一時的な障害時に自動リトライ
- SlackAPIErrorをキャッチし、リトライ処理を実行

**NFR-007**: LLM APIエラー時のフォールバック処理
- LLMAPIErrorをキャッチし、シンプルな応答を返す

#### テスト要件

- カスタム例外が正しくスローされること
- リトライ機能が指定回数リトライすること
- バックオフが正しく機能すること
- ログに適切なエラー情報が記録されること

---

## ディレクトリ構成

```
nyao/
├── config/
│   ├── __init__.py
│   └── settings.py         # 設定管理
├── core/
│   ├── __init__.py
│   ├── logging.py          # ロギングシステム
│   ├── models.py           # データモデル
│   └── exceptions.py       # カスタム例外
└── utils/
    ├── __init__.py
    └── retry.py            # リトライ機能
```

## 実装タスク

### タスク1: 設定管理システム

- [x] `config/settings.py`の実装
- [x] Pydantic Settingsの設定
- [x] 環境変数の読み込み
- [x] `.env`ファイルのサポート
- [x] テストコードの作成

### タスク2: ロギングシステム

- [x] `core/logging.py`の実装
- [x] structlogの設定
- [x] JSON形式のフォーマッター
- [x] 機密情報のマスキング処理
- [x] テストコードの作成

### タスク3: データモデル定義

- [x] `core/models.py`の実装
- [x] SlackMessageモデル
- [x] ConversationContextモデル
- [x] ResponseDecisionモデル
- [x] LLMResponseモデル
- [x] テストコードの作成

### タスク4: エラーハンドリング基盤

- [x] `core/exceptions.py`の実装
- [x] カスタム例外クラス
- [x] `utils/retry.py`の実装
- [x] リトライ機能
- [x] テストコードの作成

## テスト戦略

### ユニットテスト

**設定管理** (`tests/test_config.py`):
- 環境変数から設定が正しく読み込まれること
- デフォルト値が適用されること
- バリデーションが機能すること

**ロギング** (`tests/test_logging.py`):
- ログがJSON形式で出力されること
- 機密情報がマスキングされること

**データモデル** (`tests/test_models.py`):
- 各モデルのバリデーションが機能すること
- JSONシリアライズ・デシリアライズが動作すること

**エラーハンドリング** (`tests/test_exceptions.py`):
- カスタム例外が正しくスローされること
- リトライ機能が正しく動作すること

## 依存パッケージ

```toml
[tool.uv.dependencies]
python = "^3.12"
pydantic = "^2.0"
pydantic-settings = "^2.0"
structlog = "^23.0"
pyyaml = "^6.0"  # YAML設定ファイルの読み込み
```

## 完了条件

- [x] 必須の環境変数から設定が読み込めること
- [x] YAMLファイルから設定が読み込めること
- [x] 設定値内の環境変数参照が展開されること
- [x] LiteLLM設定がパススルーされること
- [x] 待機時間のjitterが正しく機能すること
- [x] ログが構造化形式（JSON）で出力されること
- [x] 機密情報が自動的にマスキングされること
- [x] すべてのデータモデルでバリデーションが機能すること
- [x] エラーハンドリングとリトライ機能が動作すること
- [x] すべてのユニットテストがパスすること (100件合格)
- [x] ruffによるコード品質チェックがパスすること
- [x] tyによる型チェックがパスすること

**完了日**: 2025-12-24
**品質指標**: テストカバレッジ 96%
