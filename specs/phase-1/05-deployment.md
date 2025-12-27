# レイヤー5: デプロイメントレイヤー（Deployment Layer）

## 概要

アプリケーションのエントリーポイントを提供し、すべてのコンポーネントを統合します。

## 実装優先度

**最終** - すべての機能実装後にメインアプリケーションを作成する

## 依存関係

- **依存先**: すべてのアプリケーションコード
- **依存元**: なし（最上層レイヤー）

## コンポーネント

### 1. メインアプリケーション

#### 目的

すべてのコンポーネントを統合し、アプリケーションのエントリーポイントを提供します。

#### nyao/main.py

**NyaoBotクラス**:
- `__init__()`: すべてのコンポーネントを初期化
  - Slack連携: SlackConnectionManager, EventReceiver, MessageSender, ThreadHistoryFetcher
  - LLM連携: LLMConnectionManager, PromptManager, LLMCaller
  - サービス: ResponseJudgeService, ResponseGeneratorService, ContextManagerService, ResponseDelayController
- `start()`: アプリケーションを起動
  - イベントハンドラの登録
  - Slack接続開始
  - クリーンアップループ起動
- `stop()`: アプリケーションを停止
- `_handle_message(event, say)`: メッセージイベントハンドラ
  - メッセージをコンテキストに追加
  - 応答チェックをスケジュール
- `_handle_reaction(event)`: リアクションイベントハンドラ
- `_check_and_respond(message)`: 応答チェックと応答送信
  - 応答判定
  - コンテキスト取得
  - 応答生成
  - 応答送信
- `_cleanup_loop()`: 定期クリーンアップループ（5分ごと）

**main関数**:
- ロギング設定
- NyaoBotインスタンス作成
- シグナルハンドラ設定（SIGTERM, SIGINT）
- アプリケーション起動

---

## 実装タスク

### タスク1: メインアプリケーション作成

- [x] `nyao/main.py`の実装
- [x] イベントハンドラの統合
- [x] シグナルハンドリング
- [x] エラーハンドリング
- [x] ローカルでの動作テスト

## テスト戦略

### ローカルテスト

```bash
# アプリケーション起動
uv run python -m nyao.main

# テスト実行
uv run pytest tests/test_main.py
```

## 完了条件

- [x] ログが正しく出力されること
- [x] Slack APIに接続できること
- [x] メッセージの受信・送信が動作すること
- [x] シグナルハンドリングが動作すること（SIGTERM/SIGINTで正常終了）
- [x] 全テストがパスすること

**完了日**: 2025-12-27
