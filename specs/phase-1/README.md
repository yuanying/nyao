# Phase 1: MVP仕様書

## 概要

Phase 1では、「反応がないコメントに友達のように反応する」という基本機能を実現する最小実行可能プロダクト（MVP）を開発します。

## 目標

- 指定されたSlackチャンネルのメッセージを監視
- 一定時間反応がないメッセージに対して、LLMを使用して応答すべきか判定
- 自然な応答を生成して投稿
- 複数チャンネル、スレッド対応
- Kubernetes環境での安定稼働

## 実装範囲

### 含まれる機能

- **FR-001**: 指定されたチャンネルのメッセージを監視する
- **FR-002**: メッセージ投稿後、一定時間経過しても他のユーザーから反応がない場合、応答を検討する
- **FR-003**: LLMを使用して、応答すべきかどうかを判断する
- **FR-004**: 人間らしい自然な応答を生成して投稿する
- **FR-005**: 複数の指定チャンネルで同時に動作する
- **FR-006**: スレッド内のコンテキストを理解して応答する
- **FR-007**: チャンネルごとに独立したコンテキストを管理する
- **FR-008**: 環境変数またはConfigMapで設定可能

### Phase 1の技術的特徴

- **LLMモデル**: 1つのモデルに固定（OpenAI GPT-4またはClaude）
- **メモリ管理**: 基本的なワーキングメモリ（インメモリ、永続化なし）
- **設定**: 環境変数ベース、シンプルな設定ファイル
- **データベース**: 不使用（Phase 2で導入）
- **デプロイ**: Docker + Kubernetes

### Phase 1で含まれない機能（Phase 2以降）

- 階層的記憶管理システム（ワーキングメモリ、短期記憶、長期記憶）
- データベースへの永続化
- URL・画像などのリッチコンテンツ理解
- 即座の応答判定
- LLMの動的切り替え
- 管理・制御コマンド

## アーキテクチャ概要

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
│  │ 1. Event Handler        │   │
│  │    - メッセージ受信      │   │
│  │    - 反応待機           │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ 2. Response Judge       │   │
│  │    - 応答判定           │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ 3. Response Generator   │   │
│  │    - 応答生成           │   │
│  └──────────┬──────────────┘   │
│             │                   │
│  ┌──────────▼──────────────┐   │
│  │ 4. Memory Manager       │   │
│  │    - コンテキスト管理    │   │
│  │    (インメモリ)          │   │
│  └─────────────────────────┘   │
└─────────────┬───────────────────┘
              │
    ┌─────────▼──────────────┐
    │  strands-agents        │
    │  (Agent Framework)     │
    │                        │
    │  ┌──────────────────┐  │
    │  │  LiteLLM         │  │
    │  │  - OpenAI        │  │
    │  │  - Anthropic     │  │
    │  └──────────────────┘  │
    └────────────────────────┘
```

## レイヤー構成と依存関係

Phase 1の実装は、以下の5つのレイヤーに分割されます。各レイヤーは依存関係を持ち、上位レイヤーは下位レイヤーに依存します。

### レイヤー1: 基盤レイヤー（Foundation Layer）

**実装優先度**: 最優先（すべての機能の基礎）

- 設定管理システム
- ロギングシステム
- データモデル定義（インメモリ）
- エラーハンドリング基盤

**詳細**: [01-foundation.md](./01-foundation.md)

### レイヤー2: 外部連携レイヤー（Integration Layer）

**実装優先度**: 高（基盤レイヤーの後に並行実装可能）

#### 2a. Slack連携

- Slack接続管理
- イベント受信
- メッセージ送信

**詳細**: [02-slack-integration.md](./02-slack-integration.md)

#### 2b. LLM連携

- strands-agents エージェントフレームワーク
- LiteLLM接続管理
- プロンプト管理
- LLM呼び出し

**詳細**: [03-llm-integration.md](./03-llm-integration.md)

**依存関係**: レイヤー1（基盤レイヤー）

**並行開発**: Slack連携とLLM連携は互いに独立しているため、並行して開発可能

### レイヤー3: ビジネスロジックレイヤー（Business Logic Layer）

**実装優先度**: 中（レイヤー2の後）

- 応答判定ロジック
- 応答生成ロジック
- コンテキスト管理
- 反応待機制御

**詳細**: [04-response-logic.md](./04-response-logic.md)

**依存関係**: レイヤー1（基盤レイヤー）、レイヤー2（Slack連携、LLM連携）

### レイヤー4: アプリケーションレイヤー（Application Layer）

**実装優先度**: 低（レイヤー3の後）

- メインアプリケーション
- イベントループ
- マルチチャンネル管理

**依存関係**: すべての下位レイヤー

### レイヤー5: デプロイメントレイヤー（Deployment Layer）

**実装優先度**: 最終（すべての機能実装後）

- Dockerfile
- Kubernetes manifests
- 環境設定

**詳細**: [05-deployment.md](./05-deployment.md)

**依存関係**: すべてのアプリケーションコード

## 実装計画

実装計画の詳細は [implementation-plan.md](./implementation-plan.md) を参照してください。

### 推奨実装順序

1. **Week 1**: レイヤー1（基盤レイヤー）
2. **Week 2**: レイヤー2（Slack連携 + LLM連携を並行）
3. **Week 2-3**: レイヤー3（ビジネスロジック）
4. **Week 3**: レイヤー4（アプリケーション）+ 統合テスト
5. **Week 3**: レイヤー5（デプロイメント）+ 本番環境テスト

## 成功基準

- 指定チャンネルで反応がないメッセージに対して30%以上応答
- 応答の自然さについてユーザーから肯定的なフィードバック
- 24時間以上の安定稼働
- レスポンスタイム: メッセージ受信から応答判定まで10秒以内
- 同時に10チャンネルまで監視可能

## 非機能要件

### パフォーマンス

- **NFR-001**: メッセージ受信から応答判定まで10秒以内
- **NFR-002**: 同時に複数チャンネル（最大10チャンネル）を監視可能
- **NFR-003**: LLM APIの応答待機時に他のメッセージ処理がブロックされない（非同期処理）

### 信頼性

- **NFR-006**: Slack APIの一時的な障害時に自動リトライ
- **NFR-007**: LLM APIエラー時のフォールバック処理
- **NFR-008**: Kubernetes Pod再起動時の状態復旧

### セキュリティ

- **NFR-010**: Slack APIトークンは環境変数またはKubernetes Secretで管理
- **NFR-011**: LLM APIキーは環境変数またはKubernetes Secretで管理

### 保守性

- **NFR-016**: ログ出力は構造化ログ（JSON形式）
- **NFR-018**: コードの品質はruffでチェック
- **NFR-019**: 依存関係管理はuvで統一

## 開発環境

### 必須ツール

- Python 3.12+
- uv (パッケージ管理)
- Docker
- kubectl (Kubernetes CLI)

### 推奨ツール

- ruff (Linter/Formatter)
- ty (型チェック)
- pytest (テスト)

### 環境変数

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...  # Socket Modeの場合
SLACK_CHANNEL_IDS=C123456,C789012

# LLM
LITELLM_MODEL=gpt-4
OPENAI_API_KEY=sk-...
# または
ANTHROPIC_API_KEY=sk-ant-...

# Bot Configuration
BOT_RESPONSE_DELAY=60  # 秒
BOT_PERSONA="友達のようなカジュアルな口調で話す"

# Logging
LOG_LEVEL=INFO
```

## ドキュメント構成

- [README.md](./README.md) - 本ドキュメント（Phase 1全体像）
- [01-foundation.md](./01-foundation.md) - 基盤レイヤー仕様
- [02-slack-integration.md](./02-slack-integration.md) - Slack連携仕様
- [03-llm-integration.md](./03-llm-integration.md) - LLM連携仕様
- [04-response-logic.md](./04-response-logic.md) - 応答ロジック仕様
- [05-deployment.md](./05-deployment.md) - デプロイメント仕様
- [implementation-plan.md](./implementation-plan.md) - 実装計画とタスク分割

## 参考資料

- [プロジェクト要求仕様書](../../requirements.md)
- [Slack API Documentation](https://api.slack.com/)
- [strands-agents Documentation](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo/strands-agents)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [slack-bolt Python Documentation](https://slack.dev/bolt-python/concepts)
