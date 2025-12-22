# Phase 1 実装計画

## 概要

Phase 1の実装を効率的に進めるための詳細な計画とタスク分割を記載します。並行開発を最大限活用し、約3週間でのMVP完成を目指します。

## 実装スケジュール概要

```
Week 1: 基盤レイヤー
Week 2: 外部連携レイヤー（Slack + LLM並行）
Week 2-3: ビジネスロジックレイヤー
Week 3: アプリケーション統合 + デプロイメント
```

## Week 1: 基盤レイヤー（Foundation Layer）

### 目標

すべての機能の基礎となるコンポーネントを実装し、テストを完了する。

### Day 1-2: プロジェクトセットアップと設定管理

#### タスク

1. **プロジェクト初期化**
   ```bash
   # プロジェクト構造の作成
   mkdir -p nyao/{config,core,integrations/{slack,llm},services,utils}
   mkdir -p tests/{config,core,integrations/{slack,llm},services}

   # pyproject.tomlの作成
   uv init
   ```

2. **依存パッケージのインストール**
   ```bash
   uv add pydantic pydantic-settings structlog
   uv add --dev pytest pytest-asyncio pytest-cov ruff
   ```

3. **設定管理システムの実装**
   - `config/settings.py`の実装
   - 環境変数の読み込みとバリデーション
   - `.env.example`の作成

4. **テストの作成と実行**
   ```bash
   uv run pytest tests/config/
   ```

**完了基準**:
- [ ] 設定が環境変数から正しく読み込まれる
- [ ] デフォルト値が適用される
- [ ] バリデーションエラーが検出される
- [ ] すべてのテストがパスする

---

### Day 3: ロギングシステム

#### タスク

1. **ロギングシステムの実装**
   - `core/logging.py`の実装
   - structlogの設定
   - JSON形式フォーマッター
   - 機密情報のマスキング

2. **開発環境と本番環境の切り替え**
   ```python
   setup_logging(
       log_level=settings.log_level,
       development=(settings.log_level == "DEBUG")
   )
   ```

3. **テストの作成と実行**
   ```bash
   uv run pytest tests/core/test_logging.py
   ```

**完了基準**:
- [ ] ログがJSON形式で出力される
- [ ] 機密情報が自動的にマスキングされる
- [ ] ログレベルのフィルタリングが機能する
- [ ] すべてのテストがパスする

---

### Day 4-5: データモデルとエラーハンドリング

#### タスク

1. **データモデルの実装**
   - `core/models.py`の実装
   - SlackMessage, ConversationContext, ResponseDecision, LLMResponseモデル
   - バリデーションルールの設定

2. **カスタム例外クラスの実装**
   - `core/exceptions.py`の実装
   - NyaoException, SlackAPIError, LLMAPIError等

3. **リトライ機能の実装**
   - `utils/retry.py`の実装
   - 非同期リトライ関数
   - リトライデコレータ

4. **テストの作成と実行**
   ```bash
   uv run pytest tests/core/
   uv run pytest tests/utils/
   ```

**完了基準**:
- [ ] すべてのモデルでバリデーションが機能する
- [ ] JSONシリアライズ・デシリアライズが動作する
- [ ] リトライ機能が正しく動作する
- [ ] すべてのテストがパスする

---

### Week 1 完了チェック

- [ ] ruffによるコード品質チェックがパスする
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- [ ] tyによる型チェックがパスする
  ```bash
  uv run ty check .
  ```
- [ ] テストカバレッジが80%以上
  ```bash
  uv run pytest --cov=nyao --cov-report=html
  ```

---

## Week 2: 外部連携レイヤー（Integration Layer）

### 目標

Slack連携とLLM連携を**並行して**実装し、テストを完了する。

### チーム分割（推奨）

- **担当A**: Slack連携（Day 1-5）
- **担当B**: LLM連携（Day 1-5）

単独で開発する場合は、Slack連携を優先し、その後LLM連携を実装します。

---

### Day 1-3: Slack連携の実装（担当A）

#### タスク

1. **依存パッケージのインストール**
   ```bash
   uv add slack-bolt slack-sdk
   ```

2. **Slack接続管理の実装**
   - `integrations/slack/connection.py`
   - Socket Mode接続
   - イベントハンドラ登録

3. **イベント受信の実装**
   - `integrations/slack/event_receiver.py`
   - メッセージイベント処理
   - リアクションイベント処理
   - ユーザー情報取得

4. **テストの作成**
   ```bash
   uv run pytest tests/integrations/slack/test_connection.py
   uv run pytest tests/integrations/slack/test_event_receiver.py
   ```

**完了基準**:
- [ ] Slack APIへの接続が確立できる
- [ ] メッセージイベントが受信できる
- [ ] イベントがSlackMessageモデルに変換される
- [ ] すべてのテストがパスする

---

### Day 4-5: Slack メッセージ送信とスレッド履歴（担当A）

#### タスク

1. **メッセージ送信の実装**
   - `integrations/slack/message_sender.py`
   - メッセージ送信機能
   - スレッド返信機能
   - リトライ機能

2. **スレッド履歴取得の実装**
   - `integrations/slack/thread_fetcher.py`
   - スレッドメッセージ取得
   - ユーザー情報キャッシュ

3. **テストの作成**
   ```bash
   uv run pytest tests/integrations/slack/
   ```

**完了基準**:
- [ ] メッセージが送信できる
- [ ] スレッド返信が動作する
- [ ] スレッド履歴が取得できる
- [ ] すべてのテストがパスする

---

### Day 1-3: LLM連携の実装（担当B）

#### タスク

1. **依存パッケージのインストール**
   ```bash
   uv add strands-agents litellm openai anthropic
   ```

2. **エージェント基盤の実装**
   - `integrations/llm/agent_base.py`
   - NyaoAgent基底クラス
   - LiteLLM統合
   - リトライ機能

3. **プロンプト管理の実装**
   - `integrations/llm/prompts.py`
   - 応答判定プロンプトテンプレート
   - 応答生成プロンプトテンプレート

4. **テストの作成**
   ```bash
   uv run pytest tests/integrations/llm/test_agent_base.py
   uv run pytest tests/integrations/llm/test_prompts.py
   ```

**完了基準**:
- [ ] エージェント基盤が実装できる
- [ ] LLM APIへの接続が確立できる
- [ ] プロンプトが正しく構築される
- [ ] すべてのテストがパスする

---

### Day 4-5: エージェント実装（担当B）

#### タスク

1. **応答判定エージェントの実装**
   - `integrations/llm/judge_agent.py`
   - ResponseJudgeAgentクラス
   - 応答判定ロジック
   - JSONレスポンスパース
   - フォールバック処理

2. **応答生成エージェントの実装**
   - `integrations/llm/generator_agent.py`
   - ResponseGeneratorAgentクラス
   - 応答生成ロジック
   - 応答の後処理

3. **テストの作成**
   ```bash
   uv run pytest tests/integrations/llm/test_judge_agent.py
   uv run pytest tests/integrations/llm/test_generator_agent.py
   ```

**完了基準**:
- [ ] 応答判定エージェントが動作する
- [ ] 応答生成エージェントが動作する
- [ ] フォールバック処理が動作する
- [ ] すべてのテストがパスする

---

### Week 2 完了チェック

- [ ] Slack連携のすべてのテストがパスする
- [ ] LLM連携のすべてのテストがパスする
- [ ] ruff、tyによるチェックがパスする
- [ ] 統合テストの準備（Week 3で実施）

---

## Week 2-3: ビジネスロジックレイヤー（Business Logic Layer）

### 目標

Slack連携とLLM連携を組み合わせ、アプリケーションのコアロジックを実装する。

---

### Day 1-2: 応答判定と応答生成サービス

#### タスク

1. **応答判定サービスの実装**
   - `services/response_judge.py`
   - 基本条件チェック
   - 反応状況の確認
   - LLMによる判定呼び出し

2. **応答生成サービスの実装**
   - `services/response_generator.py`
   - LLMによる応答生成
   - 応答の後処理
   - フォールバック応答

3. **テストの作成**
   ```bash
   uv run pytest tests/services/test_response_judge.py
   uv run pytest tests/services/test_response_generator.py
   ```

**完了基準**:
- [ ] 応答判定が正しく動作する
- [ ] 応答生成が正しく動作する
- [ ] フォールバック処理が動作する
- [ ] すべてのテストがパスする

---

### Day 3-4: コンテキスト管理と反応待機制御

#### タスク

1. **コンテキスト管理サービスの実装**
   - `services/context_manager.py`
   - インメモリストレージ
   - メッセージ追加・取得
   - 期限切れコンテキストのクリーンアップ

2. **反応待機制御の実装**
   - `services/delay_controller.py`
   - スケジューリング機能
   - タスクのキャンセル
   - 非同期コールバック実行

3. **テストの作成**
   ```bash
   uv run pytest tests/services/test_context_manager.py
   uv run pytest tests/services/test_delay_controller.py
   ```

**完了基準**:
- [ ] コンテキスト管理が正しく動作する
- [ ] 反応待機制御が正しく動作する
- [ ] すべてのテストがパスする

---

### Day 5: ビジネスロジックの統合テスト

#### タスク

1. **統合テストの作成**
   ```python
   # tests/integration/test_response_flow.py
   @pytest.mark.asyncio
   async def test_full_response_flow():
       """メッセージ受信から応答送信までのフルフロー"""
       pass
   ```

2. **エンドツーエンドテスト**
   - モックを使用した完全なフローのテスト
   - エラーケースのテスト

**完了基準**:
- [ ] 統合テストがパスする
- [ ] エラーハンドリングが動作する

---

## Week 3: アプリケーション統合とデプロイメント

### 目標

すべてのコンポーネントを統合し、Kubernetes環境にデプロイする。

---

### Day 1-2: メインアプリケーションの実装

#### タスク

1. **メインアプリケーションの実装**
   - `nyao/main.py`
   - NyaoBotクラス
   - イベントハンドラの統合
   - シグナルハンドリング

2. **ローカルでの動作テスト**
   ```bash
   # .envファイルの作成
   cp .env.example .env
   # 環境変数の設定後
   uv run python -m nyao.main
   ```

3. **ログ出力の確認**
   - 構造化ログが正しく出力されているか
   - エラーハンドリングが動作しているか

**完了基準**:
- [ ] アプリケーションがローカルで起動する
- [ ] Slack APIに接続できる
- [ ] メッセージの受信・送信が動作する
- [ ] ログが正しく出力される

---

### Day 3: Dockerコンテナ化

#### タスク

1. **Dockerfileの作成**
   - `Dockerfile`の作成
   - `.dockerignore`の作成
   - マルチステージビルドの実装

2. **Dockerイメージのビルド**
   ```bash
   docker build -t nyao:dev .
   ```

3. **コンテナでの動作テスト**
   ```bash
   docker run --env-file .env nyao:dev
   ```

**完了基準**:
- [ ] Dockerイメージがビルドできる
- [ ] コンテナが起動する
- [ ] コンテナ内でアプリケーションが動作する
- [ ] イメージサイズが適切（500MB以下推奨）

---

### Day 4-5: Kubernetesデプロイ

#### タスク

1. **Kubernetes Manifestsの作成**
   - `k8s/base/`配下のマニフェスト作成
   - Secret、ConfigMapの設定
   - Deploymentの設定

2. **開発環境へのデプロイ**
   ```bash
   # Secretの作成（実際の値を使用）
   kubectl create secret generic nyao-secrets \
     --from-literal=SLACK_BOT_TOKEN=xoxb-... \
     --from-literal=SLACK_APP_TOKEN=xapp-... \
     --from-literal=OPENAI_API_KEY=sk-... \
     -n nyao-dev

   # デプロイ
   kubectl apply -k k8s/overlays/development
   ```

3. **動作確認**
   ```bash
   # Pod状態確認
   kubectl get pods -n nyao-dev

   # ログ確認
   kubectl logs -f -n nyao-dev -l app=nyao

   # リソース確認
   kubectl top pod -n nyao-dev
   ```

4. **デプロイスクリプトの作成**
   - `deploy.sh`の作成
   - `undeploy.sh`の作成

**完了基準**:
- [ ] Kubernetesにデプロイできる
- [ ] Podが正常に起動する
- [ ] Slack APIに接続できる
- [ ] メッセージの受信・送信が動作する
- [ ] ログが確認できる

---

### Day 5: 本番環境準備と最終確認

#### タスク

1. **本番環境設定の作成**
   - `k8s/overlays/production/`の設定
   - リソース制限の調整
   - Secret管理の検討

2. **ドキュメントの整備**
   - README.mdの更新
   - デプロイ手順の記載
   - トラブルシューティングガイド

3. **最終動作確認**
   - 24時間の連続稼働テスト
   - エラーハンドリングの確認
   - パフォーマンスの測定

**完了基準**:
- [ ] 24時間以上の安定稼働
- [ ] メッセージへの応答率が30%以上
- [ ] 応答の品質が適切
- [ ] ドキュメントが整備されている

---

## 並行開発のための依存関係管理

### レイヤー間の依存関係

```
レイヤー1（基盤）
    ↓
レイヤー2a（Slack連携） ← 並行 → レイヤー2b（LLM連携）
    ↓
レイヤー3（ビジネスロジック）
    ↓
レイヤー4（アプリケーション）
    ↓
レイヤー5（デプロイメント）
```

### 並行開発のルール

1. **同じレイヤー内のコンポーネントは並行開発可能**
   - 例: Slack連携とLLM連携は同時に開発できる

2. **下位レイヤーが完成してから上位レイヤーを開始**
   - 例: 基盤レイヤーが完成してから外部連携レイヤーを開始

3. **インターフェースを先に定義**
   - 各コンポーネントのインターフェースを先に定義し、モックを使用してテスト

4. **Git ブランチ戦略**
   ```
   main
    ├─ feature/foundation          (Week 1)
    ├─ feature/slack-integration   (Week 2, 担当A)
    ├─ feature/llm-integration     (Week 2, 担当B)
    ├─ feature/business-logic      (Week 2-3)
    └─ feature/deployment          (Week 3)
   ```

---

## テスト戦略

### ユニットテスト

- 各コンポーネントごとに独立したテスト
- モックを使用して外部依存を排除
- カバレッジ80%以上を目標

### 統合テスト

- コンポーネント間の連携をテスト
- モックを最小限に抑える
- エラーケースを重点的にテスト

### エンドツーエンドテスト

- 実際のSlack APIとLLM APIを使用
- 開発環境で実施
- 本番環境デプロイ前に必須

### テスト実行コマンド

```bash
# すべてのテスト
uv run pytest

# ユニットテストのみ
uv run pytest tests/unit/

# 統合テストのみ
uv run pytest tests/integration/

# カバレッジレポート
uv run pytest --cov=nyao --cov-report=html

# コード品質チェック
uv run ruff check .
uv run ruff format --check .
uv run ty check .
```

---

## リスク管理

### リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| Slack API のレート制限 | 高 | リトライ機能の実装、レート制限の監視 |
| LLM API のコスト超過 | 中 | 応答頻度の制限、コスト監視 |
| Kubernetes環境の不具合 | 高 | ローカル環境での十分なテスト |
| スケジュール遅延 | 中 | 優先順位の明確化、並行開発の活用 |

---

## 成功基準（再掲）

- [ ] 指定チャンネルで反応がないメッセージに対して30%以上応答
- [ ] 応答の自然さについてユーザーから肯定的なフィードバック
- [ ] 24時間以上の安定稼働
- [ ] レスポンスタイム: メッセージ受信から応答判定まで10秒以内
- [ ] 同時に10チャンネルまで監視可能

---

## 参考資料

- [プロジェクト要求仕様書](../../requirements.md)
- [Phase 1 README](./README.md)
- 各レイヤーの詳細仕様
  - [01-foundation.md](./01-foundation.md)
  - [02-slack-integration.md](./02-slack-integration.md)
  - [03-llm-integration.md](./03-llm-integration.md)
  - [04-response-logic.md](./04-response-logic.md)
  - [05-deployment.md](./05-deployment.md)
