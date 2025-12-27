# LiteLLM直接使用への移行

## 概要

Phase 2.1では、strands-agentsを削除し、LiteLLMの`acompletion`を直接使用するエージェント基盤を実装します。これにより、依存関係を簡素化し、将来のtool call対応（Phase 3）に向けた基盤を整えます。

## 実装優先度

**最優先** - Phase 2のすべての機能がこの移行を前提としています。

## 依存関係

### 依存先
- Phase 1の基盤レイヤー（設定管理、ロギング、エラーハンドリング）
- LiteLLM パッケージ

### 依存元
- スマート応答判定（Phase 2.2-2.3）
- 階層的記憶管理（Phase 2.4）

---

## コンポーネント

### 1. NyaoAgentクラス（リファクタリング）

#### 目的

strands-agentsへの依存を削除し、LiteLLMを直接使用するエージェント基盤を提供します。

#### 機能要件

- LiteLLM `acompletion` を使用した非同期LLM呼び出し
- 構造化出力（JSON）のパース機能
- エラーハンドリングとリトライ機能
- 設定に基づくモデル・パラメータ管理

#### 実装方針

**変更前（strands-agents使用）**:
```python
from strands import Agent

class NyaoAgent:
    def __init__(self, settings: LiteLLMSettings, ...):
        self._agent = Agent(
            model=settings.model_id,
            ...
        )

    async def call_llm(self, prompt: str) -> LLMResponse:
        result = await self._agent(prompt)
        return LLMResponse(content=result.message, ...)
```

**変更後（LiteLLM直接使用）**:
```python
import litellm

class NyaoAgent:
    def __init__(self, settings: LiteLLMSettings, ...):
        self._model = settings.model_id
        self._client_args = settings.client_args
        self._params = settings.params

    async def call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature or self._params.temperature,
            max_tokens=max_tokens or self._params.max_tokens,
            **self._client_args,
        )
        return self._parse_response(response)
```

#### 主要インターフェース

```python
class NyaoAgent:
    """LiteLLMを直接使用するエージェント基盤"""

    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    RETRY_BACKOFF: float = 2.0

    def __init__(
        self,
        settings: LiteLLMSettings,
        system_prompt: str | None = None,
        skip_retry: bool = False,
    ) -> None:
        """
        エージェントを初期化する。

        Args:
            settings: LiteLLM設定
            system_prompt: システムプロンプト（オプション）
            skip_retry: リトライをスキップするか（テスト用）
        """

    async def call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        LiteLLM acompletion を呼び出す。

        Args:
            messages: メッセージリスト（role, content）
            temperature: 生成温度（オプション、設定値を上書き）
            max_tokens: 最大トークン数（オプション、設定値を上書き）

        Returns:
            LLMResponse: LLMからの応答

        Raises:
            LLMAPIError: API呼び出しに失敗した場合
        """

    async def call_llm_with_structured_output(
        self,
        messages: list[dict[str, str]],
        output_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """
        JSON出力を要求し、Pydanticモデルにパースする。

        Args:
            messages: メッセージリスト
            output_model: 出力のPydanticモデル型
            temperature: 生成温度（オプション）
            max_tokens: 最大トークン数（オプション）

        Returns:
            T: パースされたPydanticモデルインスタンス

        Raises:
            LLMAPIError: API呼び出しに失敗した場合
            ValidationError: JSONパースに失敗した場合
        """

    def _build_messages(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """
        システムプロンプトを含むメッセージリストを構築する。
        """

    def _parse_response(self, response: Any) -> LLMResponse:
        """
        LiteLLMのレスポンスをLLMResponseに変換する。
        """

    async def _call_with_retry(
        self,
        func: Callable[[], Awaitable[T]],
    ) -> T:
        """
        リトライ付きで関数を実行する。
        """
```

#### テスト要件

- [ ] `call_llm()` が正常に動作すること
- [ ] `call_llm_with_structured_output()` がJSONをパースできること
- [ ] システムプロンプトが正しく付与されること
- [ ] リトライが設定回数実行されること
- [ ] タイムアウト時に適切なエラーが発生すること
- [ ] `skip_retry=True` でリトライがスキップされること

---

### 2. ResponseJudgeAgent（更新）

#### 目的

応答判定をLiteLLM直接使用に移行し、構造化出力機能を活用します。

#### 機能要件

- FR-001: 応答判定（継続）
- FR-602: 返信先判定（新規、Phase 2.3で実装）

#### 実装方針

**変更前**:
```python
class ResponseJudgeAgent(NyaoAgent):
    async def judge(self, context: str) -> ResponseDecision:
        prompt = self._build_prompt(context)
        response = await self.call_llm(prompt)
        return self._parse_decision(response.content)
```

**変更後**:
```python
class ResponseJudgeAgent(NyaoAgent):
    async def judge(
        self,
        context: ConversationContext,
        message: SlackMessage,
    ) -> ResponseDecision:
        messages = self._build_messages_for_judgment(context, message)
        return await self.call_llm_with_structured_output(
            messages=messages,
            output_model=ResponseDecision,
        )
```

#### 主要インターフェース

```python
class ResponseJudgeAgent(NyaoAgent):
    """応答判定エージェント"""

    def __init__(
        self,
        settings: LiteLLMSettings,
        persona: str | None = None,
        skip_retry: bool = False,
    ) -> None:
        """
        応答判定エージェントを初期化する。

        Args:
            settings: LiteLLM設定
            persona: ボットのペルソナ（オプション）
            skip_retry: リトライをスキップするか
        """

    async def judge(
        self,
        context: ConversationContext,
        message: SlackMessage,
    ) -> ResponseDecision:
        """
        メッセージに対して応答すべきかを判定する。

        Args:
            context: 会話コンテキスト
            message: 判定対象のメッセージ

        Returns:
            ResponseDecision: 判定結果
        """

    def _build_messages_for_judgment(
        self,
        context: ConversationContext,
        message: SlackMessage,
    ) -> list[dict[str, str]]:
        """
        応答判定用のメッセージリストを構築する。
        """
```

#### テスト要件

- [ ] 応答判定が正しく動作すること
- [ ] ResponseDecisionが正しくパースされること
- [ ] コンテキストが正しく渡されること
- [ ] ペルソナが反映されること

---

### 3. ResponseGeneratorAgent（更新）

#### 目的

応答生成をLiteLLM直接使用に移行します。

#### 機能要件

- FR-002: 応答生成（継続）

#### 実装方針

**変更後**:
```python
class ResponseGeneratorAgent(NyaoAgent):
    async def generate(
        self,
        context: ConversationContext,
        message: SlackMessage,
    ) -> str:
        messages = self._build_messages_for_generation(context, message)
        response = await self.call_llm(messages=messages)
        return self._postprocess(response.content)
```

#### 主要インターフェース

```python
class ResponseGeneratorAgent(NyaoAgent):
    """応答生成エージェント"""

    def __init__(
        self,
        settings: LiteLLMSettings,
        persona: str | None = None,
        skip_retry: bool = False,
    ) -> None:
        """
        応答生成エージェントを初期化する。

        Args:
            settings: LiteLLM設定
            persona: ボットのペルソナ（オプション）
            skip_retry: リトライをスキップするか
        """

    async def generate(
        self,
        context: ConversationContext,
        message: SlackMessage,
    ) -> str:
        """
        メッセージに対する応答を生成する。

        Args:
            context: 会話コンテキスト
            message: 応答対象のメッセージ

        Returns:
            str: 生成された応答テキスト
        """

    def _build_messages_for_generation(
        self,
        context: ConversationContext,
        message: SlackMessage,
    ) -> list[dict[str, str]]:
        """
        応答生成用のメッセージリストを構築する。
        """

    def _postprocess(self, content: str) -> str:
        """
        生成された応答を後処理する。
        - 前後の空白を削除
        - 不要な引用符を削除
        """
```

#### テスト要件

- [ ] 応答生成が正しく動作すること
- [ ] コンテキストが正しく渡されること
- [ ] 後処理が正しく適用されること
- [ ] ペルソナが反映されること

---

### 4. PromptManager（更新）

#### 目的

プロンプトテンプレートを管理し、メッセージリスト形式での出力に対応します。

#### 実装方針

Phase 1のPromptManagerを拡張し、JSON出力形式の指示を含むプロンプトを生成します。

#### 主要インターフェース

```python
class PromptManager:
    """プロンプト管理"""

    DEFAULT_PERSONA: str = "..."

    @staticmethod
    def build_judgment_messages(
        context: ConversationContext,
        message: SlackMessage,
        persona: str | None = None,
    ) -> list[dict[str, str]]:
        """
        応答判定用のメッセージリストを構築する。

        Returns:
            list[dict[str, str]]: システムプロンプトとユーザーメッセージのリスト
        """

    @staticmethod
    def build_generation_messages(
        context: ConversationContext,
        message: SlackMessage,
        persona: str | None = None,
    ) -> list[dict[str, str]]:
        """
        応答生成用のメッセージリストを構築する。
        """

    @staticmethod
    def get_json_output_instruction(model: type[BaseModel]) -> str:
        """
        JSON出力形式の指示文を生成する。

        Args:
            model: 出力のPydanticモデル型

        Returns:
            str: JSON出力形式の指示文
        """
```

#### テスト要件

- [ ] メッセージリストが正しく構築されること
- [ ] JSON出力指示が正しく生成されること
- [ ] ペルソナが正しく反映されること

---

## ディレクトリ構成

```
nyao/
├── integrations/
│   └── llm/
│       ├── __init__.py
│       ├── agent_base.py      # NyaoAgent（リファクタリング）
│       ├── judge_agent.py     # ResponseJudgeAgent（更新）
│       ├── generator_agent.py # ResponseGeneratorAgent（更新）
│       └── prompts.py         # PromptManager（更新）
```

---

## 実装タスク

### Day 1-2: NyaoAgentクラスのリファクタリング

- [ ] `litellm` パッケージを直接依存として追加
- [ ] `NyaoAgent.__init__()` からstrands.Agent依存を削除
- [ ] `NyaoAgent.call_llm()` をメッセージリスト形式に変更
- [ ] `NyaoAgent.call_llm_with_structured_output()` を実装
- [ ] `NyaoAgent._call_with_retry()` を実装
- [ ] テストを作成・実行

### Day 3: ResponseJudgeAgentの更新

- [ ] `judge()` メソッドを更新
- [ ] `_build_messages_for_judgment()` を実装
- [ ] テストを更新・実行

### Day 4: ResponseGeneratorAgentの更新

- [ ] `generate()` メソッドを更新
- [ ] `_build_messages_for_generation()` を実装
- [ ] テストを更新・実行

### Day 5: strands-agents依存の削除

- [ ] `pyproject.toml` から `strands-agents` を削除
- [ ] 全ファイルからstrands関連のインポートを削除
- [ ] 全テストを実行
- [ ] ruff、tyによるチェック

---

## テスト戦略

### ユニットテスト

```python
# tests/integrations/llm/test_agent_base.py

@pytest.mark.asyncio
async def test_call_llm_returns_response():
    """call_llmが正しくLLMResponseを返すこと"""

@pytest.mark.asyncio
async def test_call_llm_with_structured_output_parses_json():
    """call_llm_with_structured_outputがJSONをパースすること"""

@pytest.mark.asyncio
async def test_retry_on_error():
    """エラー時にリトライが実行されること"""

@pytest.mark.asyncio
async def test_skip_retry():
    """skip_retry=Trueでリトライがスキップされること"""
```

### モック戦略

```python
@pytest.fixture
def mock_litellm_acompletion(mocker):
    """litellm.acompletionのモック"""
    return mocker.patch(
        "litellm.acompletion",
        return_value=AsyncMock(return_value=mock_response),
    )
```

---

## 依存パッケージ

### 追加

```toml
[project.dependencies]
litellm = ">=1.0.0"
```

### 削除

```toml
# 削除対象
strands-agents = "..."
```

---

## 完了条件

- [ ] NyaoAgentがLiteLLMを直接使用していること
- [ ] call_llm_with_structured_outputが実装されていること
- [ ] ResponseJudgeAgentが更新されていること
- [ ] ResponseGeneratorAgentが更新されていること
- [ ] strands-agentsへの依存がないこと
- [ ] 全テストがパスすること
- [ ] ruff、tyによるチェックがパスすること
