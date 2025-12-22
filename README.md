# Nyao

Slackワークスペースで反応がないコメントに対して友達のように反応するチャットボット。

## 概要

約10人程度の小規模ワークスペース向けに、自宅Kubernetesクラスタ上で運用することを想定したSlackボットです。

## 開発

```bash
# 依存パッケージのインストール
uv sync --dev

# テスト実行
uv run pytest

# リント・フォーマットチェック
uv run ruff check .
uv run ruff format --check .
```

## ライセンス

MIT
