# スマート応答判定

## 概要

Phase 2.2-2.3では、スマート応答判定機能を実装します。これには、リクエストごとのjitter適用、再判定機能、返信先判定が含まれます。

## 実装優先度

**高** - LiteLLM移行（Phase 2.1）完了後に実装

## 依存関係

### 依存先
- Phase 2.1: LiteLLM直接使用への移行
- Phase 1: ResponseDelayController

### 依存元
- Phase 2.4: 階層的記憶管理（MemoryContextBuilder）

---

## コンポーネント

### 1. ResponseDelayController（拡張）- jitter毎回計算

#### 目的

リクエストごとにjitterを適用し、応答タイミングをより自然にします。

#### 機能要件

- **FR-603**: レスポンス遅延時間をリクエストごとにjitter適用

#### 現状の問題

現在の実装では、jitterがNyaoBotの初期化時に一度だけ計算され、すべてのリクエストで同じ遅延時間が使用されています。

```python
# 現在の実装（main.py）
class NyaoBot:
    def __init__(self, ...):
        self._delay_seconds = settings.get_response_delay_with_jitter()
        self._delay_controller = ResponseDelayController(
            delay_seconds=self._delay_seconds,
            ...
        )
```

#### 実装方針

`schedule_response_check()` 呼び出し時に毎回jitterを計算するように変更します。

**変更後**:
```python
class ResponseDelayController:
    def __init__(
        self,
        settings: BotSettings,
        ...
    ) -> None:
        self._settings = settings
        # delay_secondsを固定値ではなく、毎回計算

    def schedule_response_check(
        self,
        message: SlackMessage,
        callback: Callable[[SlackMessage], Awaitable[Any]],
    ) -> None:
        delay = self._settings.get_response_delay_with_jitter()
        # delayを使用してスケジュール
```

#### 主要インターフェース

```python
class ResponseDelayController:
    """応答遅延制御"""

    def __init__(
        self,
        settings: BotSettings,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """
        遅延制御を初期化する。

        Args:
            settings: ボット設定（response_delay設定を含む）
            loop: イベントループ（オプション）
        """

    def schedule_response_check(
        self,
        message: SlackMessage,
        callback: Callable[[SlackMessage], Awaitable[Any]],
    ) -> None:
        """
        応答チェックをスケジュールする。
        毎回jitterを適用した遅延時間を計算する。

        Args:
            message: 対象メッセージ
            callback: 遅延後に実行するコールバック
        """

    def cancel(self, message: SlackMessage) -> bool:
        """
        スケジュールされた応答チェックをキャンセルする。

        Args:
            message: 対象メッセージ

        Returns:
            bool: キャンセルに成功した場合True
        """

    def cancel_all(self) -> int:
        """
        すべてのスケジュールされた応答チェックをキャンセルする。

        Returns:
            int: キャンセルされたタスク数
        """
```

#### テスト要件

- [ ] リクエストごとに異なる遅延時間が適用されること
- [ ] jitterの範囲が設定値内であること
- [ ] 既存のスケジュール・キャンセル機能が動作すること

---

### 2. RejudgeTracker（新規）- 再判定機能

#### 目的

「返答不要」と判定されたメッセージに対して、一定時間経過後に再判定を行います。

#### 機能要件

- **FR-601**: 返答しないと判定したメッセージに対して、一定時間経過後に再判定
  - 条件: 固定時間経過 + 新しいメッセージがない場合
  - 最大再判定回数を設定可能

#### 実装方針

新しい`RejudgeTracker`クラスを実装し、再判定のスケジューリングと追跡を行います。

```python
class RejudgeTracker:
    """再判定の追跡と管理"""

    def __init__(
        self,
        settings: RejudgeSettings,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._settings = settings
        self._loop = loop or asyncio.get_event_loop()
        self._pending_rejudges: dict[str, RejudgeInfo] = {}
        self._rejudge_counts: dict[str, int] = {}

    def schedule_rejudge(
        self,
        message: SlackMessage,
        callback: Callable[[SlackMessage], Awaitable[Any]],
    ) -> None:
        """再判定をスケジュール"""
        key = self._get_message_key(message)
        if self._rejudge_counts.get(key, 0) >= self._settings.max_count:
            return  # 最大回数に達している

        task = self._loop.call_later(
            self._settings.interval_seconds,
            lambda: asyncio.create_task(callback(message)),
        )
        self._pending_rejudges[key] = RejudgeInfo(task=task, message=message)
```

#### 設定

```python
# config/settings.py に追加

class RejudgeSettings(BaseModel):
    """再判定設定"""

    interval_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="再判定までの待機時間（秒）",
    )
    max_count: int = Field(
        default=3,
        ge=1,
        le=10,
        description="最大再判定回数",
    )
```

#### 主要インターフェース

```python
@dataclass
class RejudgeInfo:
    """再判定情報"""
    task: asyncio.TimerHandle
    message: SlackMessage
    scheduled_at: datetime


class RejudgeTracker:
    """再判定の追跡と管理"""

    def __init__(
        self,
        settings: RejudgeSettings,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """
        再判定トラッカーを初期化する。

        Args:
            settings: 再判定設定
            loop: イベントループ（オプション）
        """

    def should_rejudge(self, message: SlackMessage) -> bool:
        """
        再判定すべきか判定する。

        Args:
            message: 対象メッセージ

        Returns:
            bool: 再判定すべき場合True
        """

    def schedule_rejudge(
        self,
        message: SlackMessage,
        callback: Callable[[SlackMessage], Awaitable[Any]],
    ) -> bool:
        """
        再判定をスケジュールする。

        Args:
            message: 対象メッセージ
            callback: 再判定時に実行するコールバック

        Returns:
            bool: スケジュールに成功した場合True（最大回数超過時はFalse）
        """

    def cancel_rejudge(self, channel_id: str, thread_ts: str | None = None) -> bool:
        """
        再判定をキャンセルする（新メッセージが来た場合）。

        Args:
            channel_id: チャンネルID
            thread_ts: スレッドタイムスタンプ（オプション）

        Returns:
            bool: キャンセルに成功した場合True
        """

    def increment_count(self, message: SlackMessage) -> int:
        """
        再判定回数をインクリメントする。

        Args:
            message: 対象メッセージ

        Returns:
            int: 更新後の再判定回数
        """

    def get_count(self, message: SlackMessage) -> int:
        """
        現在の再判定回数を取得する。

        Args:
            message: 対象メッセージ

        Returns:
            int: 再判定回数
        """

    def _get_message_key(self, message: SlackMessage) -> str:
        """メッセージの一意キーを生成する"""
```

#### NyaoBotへの統合

```python
# main.py の更新

class NyaoBot:
    def __init__(self, ...):
        self._rejudge_tracker = RejudgeTracker(
            settings=settings.bot.rejudge,
        )

    async def _check_and_respond(self, message: SlackMessage) -> None:
        decision = await self._response_judge.should_respond_to_message(
            message=message,
            context=context,
        )

        if decision.should_respond:
            await self._send_response(message, context)
        else:
            # 応答しない場合、再判定をスケジュール
            if self._rejudge_tracker.should_rejudge(message):
                self._rejudge_tracker.schedule_rejudge(
                    message=message,
                    callback=self._check_and_respond,
                )
                self._rejudge_tracker.increment_count(message)

    async def _handle_message(self, event: dict) -> None:
        # 新メッセージ受信時、既存の再判定をキャンセル
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        self._rejudge_tracker.cancel_rejudge(channel_id, thread_ts)
        # 通常のメッセージ処理...
```

#### テスト要件

- [ ] 再判定がスケジュールされること
- [ ] 新メッセージで再判定がキャンセルされること
- [ ] 最大回数で再判定がスケジュールされないこと
- [ ] 再判定回数が正しくカウントされること

---

### 3. ReplyTarget enumとResponseDecision拡張 - 返信先判定

#### 目的

応答先（スレッド/チャンネル直接投稿）を判定し、適切な場所に応答を送信します。

#### 機能要件

- **FR-602**: 返信先（スレッド/チャンネル）を判定
  - 個人的な話題・既存スレッドの話題 → スレッドに返信
  - みんなに見てもらいたい内容 → チャンネルに直接投稿

#### 実装方針

`ResponseDecision`モデルを拡張し、返信先を含めます。

```python
# core/models.py に追加

class ReplyTarget(str, Enum):
    """返信先"""
    THREAD = "thread"    # スレッドに返信
    CHANNEL = "channel"  # チャンネルに直接投稿


class ResponseDecision(BaseModel):
    """応答判定結果"""

    should_respond: bool = Field(description="応答すべきか")
    reason: str = Field(description="判定理由")
    confidence: float = Field(ge=0.0, le=1.0, description="確信度")
    suggested_delay_minutes: int | None = Field(
        default=None,
        description="推奨遅延時間（分）",
    )
    reply_target: ReplyTarget = Field(
        default=ReplyTarget.THREAD,
        description="返信先（スレッド/チャンネル）",
    )
```

#### プロンプトの更新

```python
# integrations/llm/prompts.py の更新

JUDGMENT_SYSTEM_PROMPT = """
あなたは「にゃお」という名前のSlackボットです。
{persona}

以下のメッセージに対して、応答すべきかどうかを判定してください。

## 判定基準

### 応答すべき場合
- 質問や相談が含まれている
- 反応がなく寂しそうなメッセージ
- 会話が途切れている

### 応答すべきでない場合
- すでに他のユーザーが反応している
- 独り言や報告のみ
- ボット宛てでない明確な会話

## 返信先の判定

### スレッドに返信する場合 (THREAD)
- 特定の人への返答
- 既存スレッドの話題への返答
- 個人的な話題

### チャンネルに直接投稿する場合 (CHANNEL)
- みんなに見てもらいたい内容
- 新しい話題の提起
- チャンネル全体への呼びかけ

## 出力形式

JSON形式で以下を出力してください：
{json_schema}
"""
```

#### NyaoBotの更新

```python
# main.py の更新

async def _send_response(
    self,
    message: SlackMessage,
    context: ConversationContext,
    decision: ResponseDecision,
) -> None:
    response_text = await self._response_generator.generate_response(
        message=message,
        context=context,
    )

    if decision.reply_target == ReplyTarget.THREAD:
        # スレッドに返信
        await self._message_sender.send_message(
            channel=message.channel_id,
            text=response_text,
            thread_ts=message.thread_ts or message.message_id,
        )
    else:
        # チャンネルに直接投稿
        await self._message_sender.send_message(
            channel=message.channel_id,
            text=response_text,
        )
```

#### テスト要件

- [ ] ReplyTarget enumが正しく定義されていること
- [ ] ResponseDecisionにreply_targetが含まれること
- [ ] LLMがreply_targetを正しく判定すること
- [ ] スレッドへの返信が動作すること
- [ ] チャンネルへの直接投稿が動作すること

---

## ディレクトリ構成

```
nyao/
├── config/
│   └── settings.py              # RejudgeSettings追加
├── core/
│   └── models.py                # ReplyTarget enum、ResponseDecision拡張
├── integrations/
│   └── llm/
│       └── prompts.py           # 返信先判定プロンプト追加
├── services/
│   ├── delay_controller.py      # jitter毎回計算対応
│   └── rejudge_tracker.py       # 新規
└── main.py                      # RejudgeTracker統合、返信先判定対応
```

---

## 実装タスク

### Day 1-2: jitter毎回計算対応（FR-603）

- [ ] `ResponseDelayController.__init__()` のシグネチャ変更
- [ ] `schedule_response_check()` でjitter計算
- [ ] `NyaoBot.__init__()` の更新
- [ ] テストの更新・実行

### Day 3-4: 再判定機能（FR-601）

- [ ] `RejudgeSettings` の追加
- [ ] `RejudgeTracker` クラスの実装
- [ ] `NyaoBot` への統合
- [ ] テストの作成・実行

### Day 5: 返信先判定（FR-602）

- [ ] `ReplyTarget` enumの追加
- [ ] `ResponseDecision` の拡張
- [ ] プロンプトの更新
- [ ] `NyaoBot._send_response()` の更新
- [ ] テストの作成・実行

---

## テスト戦略

### ユニットテスト

```python
# tests/services/test_delay_controller.py

@pytest.mark.asyncio
async def test_jitter_varies_per_request():
    """リクエストごとにjitterが異なること"""
    delays = []
    for _ in range(10):
        controller.schedule_response_check(message, callback)
        delays.append(controller._last_delay)
    assert len(set(delays)) > 1  # 異なる値があること


# tests/services/test_rejudge_tracker.py

@pytest.mark.asyncio
async def test_schedule_rejudge():
    """再判定がスケジュールされること"""

@pytest.mark.asyncio
async def test_cancel_rejudge_on_new_message():
    """新メッセージで再判定がキャンセルされること"""

@pytest.mark.asyncio
async def test_max_rejudge_count():
    """最大回数で再判定がスケジュールされないこと"""


# tests/core/test_models.py

def test_reply_target_enum():
    """ReplyTarget enumが正しく定義されていること"""

def test_response_decision_with_reply_target():
    """ResponseDecisionにreply_targetが含まれること"""
```

---

## 完了条件

- [ ] リクエストごとにjitterが適用されていること
- [ ] 再判定機能が動作していること
  - [ ] 指定時間後に再判定が実行されること
  - [ ] 新メッセージで再判定がキャンセルされること
  - [ ] 最大回数で再判定が停止すること
- [ ] 返信先判定が動作していること
  - [ ] ReplyTarget enumが定義されていること
  - [ ] ResponseDecisionにreply_targetが含まれること
  - [ ] スレッドへの返信が動作すること
  - [ ] チャンネルへの直接投稿が動作すること
- [ ] 全テストがパスすること
- [ ] ruff、tyによるチェックがパスすること
