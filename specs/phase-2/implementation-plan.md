# Phase 2 実装計画

## 概要

Phase 2の実装を効率的に進めるための詳細な計画とタスク分割を記載します。LiteLLM直接使用への移行を基盤として、スマート応答判定と階層的記憶管理システムを約4週間で完成させることを目指します。

## 実装スケジュール概要

```
Week 1: Phase 2.1 - LiteLLM直接使用への移行
Week 2: Phase 2.2-2.3 - スマート応答判定（jitter、再判定、返信先判定）
Week 3: Phase 2.4 - 階層的記憶管理（データモデル + サービス）
Week 4: Phase 2.4 - 日次要約バッチ + 統合テスト
```

---

## Week 1: LiteLLM直接使用への移行（Phase 2.1）

### 目標

strands-agentsを削除し、LiteLLMの`acompletion`を直接使用するエージェント基盤を実装する。

### Day 1-2: 新NyaoAgentクラスの実装

#### タスク

1. **NyaoAgentクラスのリファクタリング**
   - `integrations/llm/agent_base.py` の書き換え
   - `strands.Agent` への依存を削除
   - `litellm.acompletion` を直接使用
   - `call_llm()` メソッドの再実装

2. **構造化出力メソッドの実装**
   - `call_llm_with_structured_output()` の実装
   - JSON出力を要求するプロンプト修正
   - Pydanticモデルへのパース処理

3. **エラーハンドリングとリトライ**
   - 既存のリトライロジックを移植
   - `LLMAPIError` の活用
   - タイムアウト処理

4. **テストの作成**
   ```bash
   uv run pytest tests/integrations/llm/test_agent_base.py
   ```

**完了基準**:
- [ ] `NyaoAgent.call_llm()` が動作すること
- [ ] `NyaoAgent.call_llm_with_structured_output()` が動作すること
- [ ] リトライ機能が動作すること
- [ ] すべてのテストがパスすること

---

### Day 3: ResponseJudgeAgentの更新

#### タスク

1. **ResponseJudgeAgentの更新**
   - `integrations/llm/judge_agent.py` の更新
   - `call_llm_with_structured_output()` を使用した応答判定
   - `ResponseDecision` モデルを使用した構造化出力

2. **プロンプトの調整**
   - JSON出力形式の明示的な指定
   - 出力スキーマの記述

3. **テストの作成**
   ```bash
   uv run pytest tests/integrations/llm/test_judge_agent.py
   ```

**完了基準**:
- [ ] 応答判定が正しく動作すること
- [ ] JSONパースが正常に動作すること
- [ ] 既存のテストがパスすること

---

### Day 4: ResponseGeneratorAgentの更新

#### タスク

1. **ResponseGeneratorAgentの更新**
   - `integrations/llm/generator_agent.py` の更新
   - `call_llm()` を使用した応答生成
   - フォールバック処理の維持

2. **テストの作成**
   ```bash
   uv run pytest tests/integrations/llm/test_generator_agent.py
   ```

**完了基準**:
- [ ] 応答生成が正しく動作すること
- [ ] フォールバック処理が動作すること
- [ ] 既存のテストがパスすること

---

### Day 5: strands-agents依存の削除と統合テスト

#### タスク

1. **依存関係の削除**
   - `pyproject.toml` から `strands-agents` を削除
   - 関連するインポートの削除

2. **全テストの確認**
   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv run ty check .
   ```

3. **動作確認**
   - ローカル環境での起動テスト
   - Slack APIへの接続確認

**完了基準**:
- [ ] strands-agents依存が完全に削除されていること
- [ ] すべてのテストがパスすること
- [ ] ruff、tyによるチェックがパスすること

### Week 1 完了チェック

- [ ] NyaoAgentがLiteLLMを直接使用していること
- [ ] call_llm_with_structured_outputが実装されていること
- [ ] strands-agentsへの依存がないこと
- [ ] 全テストがパスすること

---

## Week 2: スマート応答判定（Phase 2.2-2.3）

### 目標

リクエストごとのjitter適用、再判定機能、返信先判定を実装する。

### Day 1-2: jitter毎回計算対応（FR-603）

#### タスク

1. **ResponseDelayControllerの更新**
   - `services/delay_controller.py` の更新
   - `schedule_response_check()` 呼び出し時に毎回jitterを計算
   - 既存のコンストラクタでの一回計算を削除

2. **設定の確認**
   - `BotSettings.response_delay` の設定確認
   - jitter範囲の調整

3. **テストの作成**
   ```bash
   uv run pytest tests/services/test_delay_controller.py
   ```

**完了基準**:
- [ ] リクエストごとにjitterが適用されること
- [ ] 遅延時間がランダムに変動すること
- [ ] テストがパスすること

---

### Day 3-4: 再判定機能（FR-601）

#### タスク

1. **RejudgeTrackerクラスの実装**
   - `services/rejudge_tracker.py` の新規作成
   - 「返答不要」判定されたメッセージの追跡
   - 再判定回数のカウント
   - 最大再判定回数の管理

2. **設定の追加**
   - `config/settings.py` に `RejudgeSettings` を追加
   ```python
   class RejudgeSettings(BaseModel):
       interval_seconds: int = 300  # 5分後に再判定
       max_count: int = 3  # 最大3回まで再判定
   ```

3. **NyaoBotへの統合**
   - `main.py` の `_check_and_respond()` を更新
   - 「返答不要」判定後、再判定スケジュールを設定
   - 新メッセージ受信時の再判定キャンセル

4. **テストの作成**
   ```bash
   uv run pytest tests/services/test_rejudge_tracker.py
   ```

**完了基準**:
- [ ] 再判定機能が動作すること
- [ ] 新メッセージで再判定がスキップされること
- [ ] 最大回数で再判定が停止すること
- [ ] テストがパスすること

---

### Day 5: 返信先判定（FR-602）

#### タスク

1. **ReplyTarget enumの追加**
   - `core/models.py` に追加
   ```python
   class ReplyTarget(str, Enum):
       THREAD = "thread"
       CHANNEL = "channel"
   ```

2. **ResponseDecisionモデルの拡張**
   ```python
   class ResponseDecision(BaseModel):
       should_respond: bool
       reason: str
       confidence: float
       suggested_delay_minutes: int | None = None
       reply_target: ReplyTarget = ReplyTarget.THREAD
   ```

3. **プロンプトの更新**
   - `integrations/llm/prompts.py` の更新
   - 返信先判定の指示を追加
   - 判定基準の明示

4. **NyaoBotの更新**
   - `_check_and_respond()` の更新
   - `reply_target` に基づいて送信先を決定

5. **テストの作成**
   ```bash
   uv run pytest tests/integrations/llm/test_judge_agent.py
   uv run pytest tests/test_main.py
   ```

**完了基準**:
- [ ] 返信先判定が正しく動作すること
- [ ] スレッドへの返信が動作すること
- [ ] チャンネルへの直接投稿が動作すること
- [ ] テストがパスすること

### Week 2 完了チェック

- [ ] リクエストごとにjitterが適用されていること
- [ ] 再判定機能が動作していること
- [ ] 返信先判定が動作していること
- [ ] 全テストがパスすること

---

## Week 3: 階層的記憶管理システム - データモデル + サービス（Phase 2.4 前半）

### 目標

SQLModelを使用したデータモデルと記憶層サービスを実装する。

### Day 1-2: データモデル定義とデータベース初期化

#### タスク

1. **memoryディレクトリの作成**
   ```bash
   mkdir -p nyao/memory
   touch nyao/memory/__init__.py
   ```

2. **データモデルの実装**
   - `memory/models.py` の作成
   - `WorkingMemoryMessage`
   - `ThreadSummary`
   - `ChannelDailySummary`
   - `WorkspaceMemory`
   - `ChannelLongTermMemory`
   - `UserLongTermMemory`

3. **データベース初期化**
   - `memory/database.py` の作成
   - SQLite接続管理
   - テーブル作成
   - 非同期セッション管理

4. **依存パッケージの追加**
   ```bash
   uv add sqlmodel aiosqlite
   ```

5. **テストの作成**
   ```bash
   uv run pytest tests/memory/test_models.py
   uv run pytest tests/memory/test_database.py
   ```

**完了基準**:
- [ ] すべてのモデルが定義されていること
- [ ] データベースが正しく初期化されること
- [ ] CRUD操作が動作すること
- [ ] テストがパスすること

---

### Day 3-4: 記憶層サービスの実装

#### タスク

1. **ワーキングメモリサービス**
   - `memory/working_memory.py` の作成
   - メッセージの保存・取得
   - LiteLLMメッセージ形式への変換
   - 過去X日分のフィルタリング
   - 古いメッセージの削除

2. **短期記憶サービス**
   - `memory/short_term.py` の作成
   - スレッド要約の保存・取得
   - チャンネル日次要約の保存・取得

3. **長期記憶サービス**
   - `memory/long_term.py` の作成
   - ワークスペース記憶の保存・取得
   - チャンネル特性の保存・取得
   - ユーザー特性の保存・取得

4. **テストの作成**
   ```bash
   uv run pytest tests/memory/test_working_memory.py
   uv run pytest tests/memory/test_short_term.py
   uv run pytest tests/memory/test_long_term.py
   ```

**完了基準**:
- [ ] 各記憶層のCRUD操作が動作すること
- [ ] LiteLLMメッセージ形式への変換が正しいこと
- [ ] テストがパスすること

---

### Day 5: MemoryContextBuilderの実装

#### タスク

1. **MemoryContextBuilderの実装**
   - `memory/context_builder.py` の作成
   - 階層的記憶を組み合わせてプロンプトコンテキストを構築
   - トークン数の推定と制限（8000トークン以内）
   - 優先順位に基づく記憶の選択

2. **既存サービスとの統合準備**
   - `ContextManagerService` との連携方針決定
   - インメモリ管理からDB永続化への段階的移行

3. **テストの作成**
   ```bash
   uv run pytest tests/memory/test_context_builder.py
   ```

**完了基準**:
- [ ] プロンプトコンテキストが正しく構築されること
- [ ] トークン数制限が守られること
- [ ] テストがパスすること

### Week 3 完了チェック

- [ ] すべてのデータモデルが定義されていること
- [ ] データベース初期化が動作すること
- [ ] 各記憶層サービスが動作すること
- [ ] MemoryContextBuilderが動作すること
- [ ] 全テストがパスすること

---

## Week 4: 日次要約バッチ + 統合テスト（Phase 2.4 後半）

### 目標

要約生成機能とバッチ処理を実装し、全体を統合する。

### Day 1-2: MemorySummarizerの実装

#### タスク

1. **MemorySummarizerの実装**
   - `memory/summarizer.py` の作成
   - スレッド要約生成
   - チャンネル日次要約生成
   - ワークスペース要約更新
   - チャンネル特性更新
   - ユーザー特性更新

2. **プロンプトテンプレートの作成**
   - `integrations/llm/prompts.py` に要約用プロンプトを追加
   - スレッド要約用
   - チャンネル日次要約用
   - チャンネル特性抽出用
   - ユーザー特性抽出用

3. **テストの作成**
   ```bash
   uv run pytest tests/memory/test_summarizer.py
   ```

**完了基準**:
- [ ] 各種要約が正しく生成されること
- [ ] LLMを使用した要約が動作すること
- [ ] テストがパスすること

---

### Day 3: 日次要約バッチ処理

#### タスク

1. **BatchProcessorの実装**
   - `memory/batch_processor.py` の作成
   - 10分間隔での実行ループ
   - チャンネルごとの変更検知（最終更新時刻を追跡）
   - 当日分の更新処理
   - 過去X日分の作成処理

2. **NyaoBotへの統合**
   - `main.py` の更新
   - バッチ処理ループの起動
   - グレースフルシャットダウン対応

3. **テストの作成**
   ```bash
   uv run pytest tests/memory/test_batch_processor.py
   ```

**完了基準**:
- [ ] バッチ処理が正常に実行されること
- [ ] 変更検知が動作すること
- [ ] グレースフルシャットダウンが動作すること
- [ ] テストがパスすること

---

### Day 4-5: 統合テストと最終調整

#### タスク

1. **統合テストの実施**
   - メッセージ受信から応答送信までのフルフロー
   - 記憶管理の統合テスト
   - 再判定機能の統合テスト

2. **パフォーマンス確認**
   - コンテキスト構築時間の測定
   - トークン使用量の確認
   - データベースクエリの最適化

3. **コード品質チェック**
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run ty check .
   uv run pytest --cov=nyao
   ```

4. **ドキュメントの整備**
   - README.mdの更新（Phase 2完了を反映）

**完了基準**:
- [ ] 過去の会話を踏まえた応答が50%以上
- [ ] コンテキストウィンドウが8000トークン以内
- [ ] すべてのテストがパスすること
- [ ] ruff、tyによるチェックがパスすること

### Week 4 完了チェック

- [ ] MemorySummarizerが動作すること
- [ ] BatchProcessorが動作すること
- [ ] 統合テストがパスすること
- [ ] 全テストがパスすること

---

## テスト戦略

### ユニットテスト

- 各コンポーネントごとに独立したテスト
- モックを使用して外部依存を排除
- カバレッジ80%以上を目標

### 統合テスト

- コンポーネント間の連携をテスト
- SQLiteを使用した実際のDB操作テスト
- LLM APIはモックを使用

### テスト実行コマンド

```bash
# すべてのテスト
uv run pytest

# 特定のモジュールのテスト
uv run pytest tests/memory/
uv run pytest tests/services/

# カバレッジレポート
uv run pytest --cov=nyao --cov-report=html

# コード品質チェック
uv run ruff check .
uv run ruff format --check .
uv run ty check .
```

---

## 依存パッケージ

### 追加するパッケージ

```toml
[project.dependencies]
sqlmodel = ">=0.0.22"
aiosqlite = ">=0.19.0"
# litellmは既存（strands-agents経由で入っていたものを直接依存に変更）
litellm = ">=1.0.0"

[dependency-groups.dev]
# 既存のパッケージに加えて
pytest-asyncio = ">=0.23.0"
```

### 削除するパッケージ

```toml
# 削除対象
strands-agents = "..."  # Week 1 Day 5 で削除
```

---

## リスク管理

| リスク | 影響 | 対策 |
|--------|------|------|
| LiteLLM APIの変更 | 中 | バージョン固定、テスト充実 |
| トークン数超過 | 高 | 段階的な記憶圧縮、優先順位管理 |
| SQLiteパフォーマンス | 低 | インデックス最適化、クエリ効率化 |
| バッチ処理の負荷 | 中 | 処理間隔の調整、並行処理の検討 |

---

## 成功基準（再掲）

- [ ] strands-agents依存が完全に削除されている
- [ ] リクエストごとにjitterが適用されている
- [ ] 再判定機能が動作している
- [ ] 返信先判定が正しく動作している
- [ ] 階層的記憶管理が動作し、プロンプトに反映されている
- [ ] 日次要約バッチが正常に実行されている
- [ ] 過去の会話を踏まえた応答が50%以上
- [ ] コンテキストウィンドウの効率的な使用（8000トークン以内）
- [ ] 既存のテストがすべてパスしている
- [ ] ruff、tyによるコード品質チェックがパスしている

---

## 参考資料

- [プロジェクト要求仕様書](../../requirements.md)
- [Phase 2 README](./README.md)
- 各レイヤーの詳細仕様
  - [01-litellm-migration.md](./01-litellm-migration.md)
  - [02-smart-response.md](./02-smart-response.md)
  - [03-memory-models.md](./03-memory-models.md)
  - [04-memory-services.md](./04-memory-services.md)
  - [05-batch-processing.md](./05-batch-processing.md)
