# レイヤー2b: LLM連携レイヤー（LLM Integration Layer）

## 概要

strands-agentsエージェントフレームワークとLiteLLMを使用してLLM APIとの連携を担当し、応答判定と応答生成のためのLLM呼び出しを行います。strands-agentsを使用することで、エージェント的な処理フローを構造化し、再利用可能な形で実装します。

## 実装優先度

**高** - 基盤レイヤーの後に実装。Slack連携と並行実装可能。

## 依存関係

- **依存先**: レイヤー1（基盤レイヤー）
  - 設定管理システム
  - ロギングシステム
  - データモデル
  - エラーハンドリング
- **依存元**: レイヤー3（ビジネスロジックレイヤー）
- **並行実装可能**: Slack連携レイヤー（レイヤー2a）と独立

## strands-agentsについて

strands-agentsは、LLMエージェントを構築するためのフレームワークです。以下の特徴があります：

- **構造化されたエージェント定義**: エージェントのロジックを明確に定義
- **再利用性**: エージェントコンポーネントの再利用
- **テスト容易性**: エージェントのロジックを独立してテスト可能
- **LiteLLM統合**: LiteLLMと組み合わせて複数のLLMプロバイダーに対応

Phase 1では、strands-agentsを使用して応答判定エージェントと応答生成エージェントを実装します。

## Phase 1でのLLMモデル

Phase 1では、設定ファイルでLiteLLMの設定を直接扱うことで、モデルの切り替えが可能です。
以下のようなモデルを使用できます：
- **OpenAI GPT-4** (推奨)
- **Anthropic Claude 3.5 Sonnet**
- その他LiteLLMがサポートする任意のモデル

設定ファイルで `litellm.model` を変更するだけで、簡単にモデルを切り替えられます。

## コンポーネント

### 1. エージェント基盤 (Agent Foundation)

#### 目的

strands-agentsを使用したエージェント基盤を構築し、すべてのエージェントで共通して使用する機能を提供する。

#### 主要インターフェース

**NyaoAgentクラス** (strands-agentsのAgentをラップ):
- `__init__(settings, system_prompt)`: LiteLLMSettingsとシステムプロンプトで初期化
- `call_llm(prompt, temperature, max_tokens)`: strands.Agentを使用してLLMを呼び出す

#### テスト要件

- エージェント基盤が正しく初期化されること
- LLM呼び出しが正しく動作すること

---

### 2. 応答判定エージェント (Response Judge Agent)

#### 目的

Slackメッセージに対して応答すべきかどうかを判定するエージェント。strands-agentsのAgent基底クラスを継承して実装します。

#### Phase 2以降の拡張を見据えた設計

Phase 1では「応答すべきかどうか」のみを判定しますが、Phase 2以降では以下の追加判定が可能になるよう設計します：
- **応答タイミング**: 何分後に応答すべきか
- **応答の優先度**: 緊急度に応じた優先順位付け
- **応答のトーン**: 状況に応じた口調の調整

このため、応答判定の出力形式は拡張可能な構造とし、Phase 2で追加フィールドを容易に追加できるようにします。

#### プロンプトテンプレート

**応答判定プロンプト** (`SHOULD_RESPOND_PROMPT`):
- メッセージ情報（チャンネル、投稿者、メッセージ本文等）を含む
- 現在の状況（経過時間、反応数、返信数）
- 応答すべき場合/すべきでない場合の例
- JSON形式で回答を要求（`should_respond`, `reason`, `confidence`）
  - Phase 2拡張用の予約フィールド: `suggested_delay_minutes` (Phase 1では未使用)

**応答生成プロンプト** (`RESPONSE_GENERATION_PROMPT`):
- ボットのペルソナ設定
- 返信ガイドライン（カジュアルな口調、1-3文程度等）
- 会話のコンテキスト（過去の会話履歴）
- 返信対象のメッセージ

#### 主要インターフェース

**PromptManagerクラス**:
- `__init__(persona)`: 初期化
- `build_should_respond_prompt(message, elapsed_seconds, reaction_count, reply_count)`: 応答判定用プロンプト文字列を構築して返す
- `build_response_generation_prompt(message, context)`: 応答生成用プロンプト文字列を構築して返す

#### テスト要件

- プロンプトが正しく構築されること
- コンテキスト情報が適切に含まれること
- ペルソナ設定が反映されること

---

### 3. LLM呼び出しラッパー (LLM Caller)

#### 目的

プロンプト管理とLLM接続を組み合わせ、高レベルなLLM呼び出しインターフェースを提供する。

#### インターフェース

**LLMCallerクラス**:
- `__init__(connection_manager, prompt_manager)`: 初期化
- `judge_should_respond(message, elapsed_seconds, reaction_count, reply_count)`: 応答すべきかどうかを判定し、ResponseDecisionを返す
  - temperature=0.3で一貫性を重視
  - max_tokens=200
- `generate_response(message, context)`: 応答メッセージを生成し、LLMResponseを返す
  - temperature=0.8で多様性を重視
  - max_tokens=300
- `_parse_json_response(content)`: LLMのJSON形式レスポンスをパース

#### フォールバック戦略

**NFR-007**: LLM APIエラー時のフォールバック処理

1. **応答判定エラー時**: デフォルトで「応答しない」を返す（安全側に倒す）
2. **応答生成エラー時**: 例外をスローして上位レイヤーで処理
3. **リトライ**: 最大3回まで自動リトライ

#### テスト要件

- 応答判定が正しく動作すること
- 応答生成が正しく動作すること
- JSON形式のレスポンスが正しくパースされること
- エラー時のフォールバックが動作すること

---

## ディレクトリ構成

```
nyao/
└── integrations/
    └── llm/
        ├── __init__.py
        ├── agent_base.py       # NyaoAgent（基底エージェントクラス）
        ├── judge_agent.py      # ResponseJudgeAgent（応答判定エージェント）
        ├── generator_agent.py  # ResponseGeneratorAgent（応答生成エージェント）
        └── prompts.py          # プロンプトテンプレート
```

## 実装タスク

### タスク1: エージェント基盤

- [ ] `integrations/llm/agent_base.py`の実装
- [ ] NyaoAgent基底クラス
- [ ] LiteLLM統合
- [ ] リトライ機能
- [ ] テストコードの作成

### タスク2: プロンプト管理

- [ ] `integrations/llm/prompts.py`の実装
- [ ] 応答判定プロンプトテンプレート
- [ ] 応答生成プロンプトテンプレート
- [ ] テストコードの作成

### タスク3: 応答判定エージェント

- [ ] `integrations/llm/judge_agent.py`の実装
- [ ] ResponseJudgeAgentクラス
- [ ] 応答判定ロジック
- [ ] JSONレスポンスパース
- [ ] フォールバック処理
- [ ] テストコードの作成

### タスク4: 応答生成エージェント

- [ ] `integrations/llm/generator_agent.py`の実装
- [ ] ResponseGeneratorAgentクラス
- [ ] 応答生成ロジック
- [ ] 応答の後処理
- [ ] テストコードの作成

## テスト戦略

### ユニットテスト

**tests/integrations/llm/test_connection.py**:
- LLM呼び出しが正常に動作すること
- エラー時にリトライが動作すること

**tests/integrations/llm/test_prompts.py**:
- 応答判定プロンプトが正しく構築されること
- 応答生成プロンプトが正しく構築されること

**tests/integrations/llm/test_caller.py**:
- 応答判定が正しく動作すること
- 応答生成が正しく動作すること
- エラー時のフォールバックが動作すること

### モックの使用

LLM APIへの実際の通信は行わず、`unittest.mock.AsyncMock`と`patch`を使用してテストします。

## 依存パッケージ

```toml
[tool.uv.dependencies]
strands-agents = "^0.1"  # エージェントフレームワーク
litellm = "^1.0"  # LLMプロバイダー統合
openai = "^1.0"  # OpenAI API（LiteLLMの依存）
anthropic = "^0.25"  # Anthropic Claude API
```

## プロンプトチューニング

Phase 1では基本的なプロンプトを使用しますが、以下の改善を継続的に行います：

1. **応答品質の評価**: 生成された応答の品質を人間が評価
2. **プロンプトの調整**: フィードバックに基づいてプロンプトを改善
3. **温度パラメータの調整**: 応答の多様性と一貫性のバランス調整
4. **Few-shot学習**: 必要に応じて例を追加

## 完了条件

- [ ] LLM APIへの接続が確立できること
- [ ] 応答判定が動作すること
- [ ] 応答生成が動作すること
- [ ] プロンプトが適切に構築されること
- [ ] リトライ機能が動作すること
- [ ] フォールバック処理が動作すること
- [ ] すべてのユニットテストがパスすること
- [ ] ruffによるコード品質チェックがパスすること
- [ ] tyによる型チェックがパスすること

## 参考資料

- [strands-agents Documentation](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo/strands-agents)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Anthropic Claude API](https://docs.anthropic.com/)
