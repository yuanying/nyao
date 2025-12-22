# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Nyao - Slackワークスペースで反応がないコメントに対して友達のように反応するチャットボット。
約10人程度の小規模ワークスペース向けに、自宅Kubernetesクラスタ上で運用することを想定。

MVP原則に基づき、まずは最小限の機能セットでリリースし、段階的に機能を拡張していく。

## 要求仕様書

[要求仕様書](./requirements.md) を参照。

## 機能仕様書

各フェーズごとの機能仕様書が [仕様書ディレクトリ](specs/) に格納されている。

## 開発哲学

### テスト駆動開発（TDD）

テストおよびリント、型チェックをコード変更ごとに必ず実行する。

```bash
uv run ruff check . --fix
uv run ruff format --check .
uv run ty check .
uv run pytest
```

## 技術スタック

### コア技術
- **言語**: Python 3.12+
- **パッケージ管理**: uv

### 主要ライブラリ
- **Slack連携**: slack-sdk または slack-bolt
- **LLM連携**: strands-agents + litellm（複数のLLMプロバイダー対応）
- **非同期処理**: asyncio + aiohttp
- **データベース**:
  - Phase 1: SQLite（MVP）
  - Phase 2: PostgreSQL（本番環境）
- **ORマッパー**: SQLModel（SQLAlchemy 2.0 + Pydantic統合）
- **ロギング**: structlog（構造化ログ、JSON形式）

## システムアーキテクチャ

### 全体構成
```
Slack API → Slack Bot (Python App) → LiteLLM / Database / Memory Manager
```

### 階層的記憶管理システム（Phase 2以降）
- **ワーキングメモリ**: 現在進行中の会話（30分〜1時間、最大50件）
- **短期記憶**: 最近の会話要約（過去1〜7日間）
- **長期記憶**: 高度に圧縮された本質的情報（永続的）

### データモデル
SQLModelを使用した型安全なモデル定義。Pydanticのバリデーション機能を活用。
主要テーブル:
- `working_memory`: リアルタイムメッセージ
- `thread_summaries`: スレッド単位の要約
- `channel_daily_summaries`: チャンネルの日次要約
- `channel_long_term_memory`: チャンネル特性
- `user_long_term_memory`: ユーザー特性
- `knowledge_entries`: 知識ベース

## 環境変数

`.env` ファイルにて管理する。

```bash
source .env
```

## 開発フェーズ

現在の開発フェーズを確認し、フェーズに応じたタスクを優先的に処理する。
