# レイヤー3: ビジネスロジックレイヤー（Business Logic Layer）

## 概要

Slack連携とLLM連携を組み合わせ、アプリケーションのコアロジックを実装します。メッセージへの応答判定、応答生成、コンテキスト管理を担当します。

## 実装優先度

**中** - レイヤー2（Slack連携、LLM連携）の後に実装

## 依存関係

- **依存先**:
  - レイヤー1（基盤レイヤー）
  - レイヤー2a（Slack連携レイヤー）
  - レイヤー2b（LLM連携レイヤー）
- **依存元**: レイヤー4（アプリケーションレイヤー）

## コンポーネント

### 1. 応答判定サービス (Response Judge Service)

#### 目的

メッセージに対して応答すべきかどうかを総合的に判定します。

#### 機能要件

- **FR-002**: メッセージ投稿後、一定時間経過しても他のユーザーから反応がない場合、応答を検討する
- **FR-003**: LLMを使用して、応答すべきかどうかを判断する

#### 判定フロー

```
メッセージ受信
    ↓
基本条件チェック
    ↓
反応待機（設定された時間）
    ↓
反応状況の確認
    ↓
LLMによる判定
    ↓
応答判定結果
```

#### インターフェース

**ResponseJudgeServiceクラス**:
- `__init__(llm_caller, response_delay=60)`: 初期化
- `should_respond_to_message(message, reactions, reply_count)`: メッセージに応答すべきか判定し、ResponseDecisionを返す
  - 基本条件チェック（空メッセージ、短すぎるメッセージを除外）
  - リアクション数、返信数はLLMの判定材料として渡す（事前に拒否しない）
  - LLMによる判定を実行
- `_check_basic_conditions(message)`: 基本条件チェック（メッセージが空でない、3文字以上）
- `_calculate_elapsed_time(message)`: メッセージ投稿からの経過時間を計算

#### テスト要件

- 基本条件チェックが正しく動作すること
- リアクション数、返信数がLLMに正しく渡されること
- LLMによる判定が正しく実行されること
- 経過時間が正しく計算されること

---

### 2. 応答生成サービス (Response Generator Service)

#### 目的

LLMを使用して、適切な応答メッセージを生成します。

#### 機能要件

- **FR-004**: 人間らしい自然な応答を生成して投稿する
- **FR-006**: スレッド内のコンテキストを理解して応答する
- **FR-006a**: スレッドに属さないチャンネル内の過去メッセージも参照してコンテキストを理解する

#### インターフェース

**ResponseGeneratorServiceクラス**:
- `__init__(llm_caller)`: 初期化
- `generate_response(message, thread_context, channel_context)`: 応答メッセージを生成し、文字列を返す
  - スレッドコンテキストとチャンネルコンテキストの両方を参照
  - LLMで応答を生成
  - 後処理を適用
  - エラー時はフォールバック応答を返す
- `_post_process_response(response)`: 応答の後処理（空白削除、引用符削除、長さ制限500文字）
- `_get_fallback_response()`: フォールバック応答をランダムに返す（「そうなんだね！」「なるほど」等）

#### テスト要件

- 応答が正しく生成されること
- スレッドコンテキストが正しく反映されること
- チャンネルコンテキストが正しく反映されること
- 後処理が正しく動作すること（引用符削除、長さ制限等）
- フォールバック応答が返されること

---

### 3. コンテキスト管理サービス (Context Manager Service)

#### 目的

チャンネルおよびスレッドごとの会話コンテキストをインメモリで管理します。

#### 機能要件

- **FR-006**: スレッド内のコンテキストを理解して応答する
- **FR-006a**: スレッドに属さないチャンネル内の過去メッセージも参照してコンテキストを理解する
- **FR-007**: チャンネルごとに独立したコンテキストを管理する

#### Phase 1でのコンテキスト管理

- **インメモリ**: データベースを使用せず、メモリ上で管理
- **保持期間**: 最大1時間（設定可能）
- **保持件数**: スレッドあたり最大50件（設定可能）

#### インターフェース

**ContextManagerServiceクラス**:
- `__init__(max_context_age_seconds=3600, max_messages_per_context=50, max_channel_context_messages=20)`: 初期化
  - インメモリストレージ: `Dict[str, ConversationContext]`
  - キー形式: `"channel_id:thread_ts"` または `"channel_id"`
- `get_context(channel_id, thread_ts)`: コンテキストを取得（期限切れの場合は削除してNoneを返す）
- `get_channel_context(channel_id)`: チャンネルレベルのコンテキストを取得（スレッドに属さないメッセージ）
- `add_message(message)`: メッセージをコンテキストに追加
  - 新規コンテキストを自動作成
  - メッセージ数が上限を超えたら古いものから削除
  - スレッドに属さないメッセージはチャンネルコンテキストにも追加
- `cleanup_expired_contexts()`: 期限切れのコンテキストをクリーンアップし、削除数を返す
- `_make_context_key(channel_id, thread_ts)`: コンテキストキーを生成
- `_is_context_expired(context)`: コンテキストが期限切れか判定
- `get_statistics()`: 統計情報を取得（コンテキスト総数、設定値等）

#### 定期クリーンアップ

アプリケーションレイヤーで定期的に`cleanup_expired_contexts()`を呼び出します（例: 5分ごと）。

#### テスト要件

- コンテキストが正しく作成されること
- メッセージが正しく追加されること
- チャンネルコンテキストが正しく取得できること
- スレッドに属さないメッセージがチャンネルコンテキストに含まれること
- 古いコンテキストが削除されること
- メッセージ数の制限が機能すること
- クリーンアップが正しく動作すること

---

### 4. 反応待機制御 (Response Delay Controller)

#### 目的

メッセージ受信後、設定された時間だけ待機してから応答判定を行います。

#### 機能要件

- **FR-002**: メッセージ投稿後、一定時間経過しても他のユーザーから反応がない場合、応答を検討する

#### インターフェース

**ResponseDelayControllerクラス**:
- `__init__(delay_seconds=60)`: 初期化
  - 待機中のタスク管理: `Dict[str, asyncio.Task]`
- `schedule_response_check(message, callback)`: 応答チェックをスケジュール
  - 既存のタスクがあればキャンセル
  - 新しい非同期タスクを作成
- `cancel_response_check(message)`: 応答チェックをキャンセルし、成功したかどうかを返す
- `_delayed_callback(message, callback)`: 遅延コールバック
  - 指定時間待機後にコールバックを実行
  - `asyncio.CancelledError`をハンドリング
- `_make_task_key(message)`: タスクキーを生成（`"channel_id:message_id"`）
- `get_pending_count()`: 待機中のタスク数を取得

#### 待機のキャンセル条件

以下の場合、待機中のタスクをキャンセルします：
- 他のユーザーがメッセージに返信した
- 他のユーザーがリアクションを追加した

#### テスト要件

- 応答チェックが正しくスケジュールされること
- 待機時間が正しく動作すること
- タスクのキャンセルが正しく動作すること
- コールバックが正しく実行されること

---

## ディレクトリ構成

```
nyao/
└── services/
    ├── __init__.py
    ├── response_judge.py       # ResponseJudgeService
    ├── response_generator.py   # ResponseGeneratorService
    ├── context_manager.py      # ContextManagerService
    └── delay_controller.py     # ResponseDelayController
```

## 実装タスク

### タスク1: 応答判定サービス

- [ ] `services/response_judge.py`の実装
- [ ] 基本条件チェック
- [ ] 反応状況をLLMに渡す
- [ ] LLMによる判定呼び出し
- [ ] テストコードの作成

### タスク2: 応答生成サービス

- [ ] `services/response_generator.py`の実装
- [ ] LLMによる応答生成
- [ ] 応答の後処理
- [ ] フォールバック応答
- [ ] テストコードの作成

### タスク3: コンテキスト管理サービス

- [ ] `services/context_manager.py`の実装
- [ ] インメモリストレージ
- [ ] メッセージ追加・取得
- [ ] 期限切れコンテキストのクリーンアップ
- [ ] テストコードの作成

### タスク4: 反応待機制御

- [ ] `services/delay_controller.py`の実装
- [ ] スケジューリング機能
- [ ] タスクのキャンセル
- [ ] 非同期コールバック実行
- [ ] テストコードの作成

## テスト戦略

### ユニットテスト

**tests/services/test_response_judge.py**:
- 基本条件チェックが正しく動作すること
- リアクション数、返信数がLLMに渡されること

**tests/services/test_response_generator.py**:
- 応答が正しく生成されること
- 後処理が正しく動作すること

**tests/services/test_context_manager.py**:
- メッセージが正しく追加されること
- 期限切れコンテキストが削除されること

**tests/services/test_delay_controller.py**:
- 応答チェックが正しくスケジュールされること
- タスクのキャンセルが動作すること

## 完了条件

- [ ] 応答判定が正しく動作すること
- [ ] 応答生成が正しく動作すること
- [ ] コンテキスト管理が正しく動作すること
- [ ] 反応待機制御が正しく動作すること
- [ ] すべてのユニットテストがパスすること
- [ ] ruffによるコード品質チェックがパスすること
- [ ] tyによる型チェックがパスすること
