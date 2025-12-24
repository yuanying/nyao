"""データモデル定義

Phase 1で使用する主要なデータモデルを定義します。
すべてのモデルはPydantic BaseModelを継承し、型安全性とバリデーションを提供します。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class SlackMessage(BaseModel):
    """Slackメッセージモデル

    Slackから受信したメッセージの情報を保持します。
    """

    model_config = ConfigDict()

    message_id: str
    channel_id: str
    thread_ts: str | None = None
    user_id: str
    user_name: str
    text: str
    timestamp: datetime
    reactions: list[str] = Field(default_factory=list)
    reply_count: int = 0

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """timestampをISO8601形式の文字列にシリアライズ"""
        return value.isoformat()


class ConversationContext(BaseModel):
    """会話コンテキストモデル

    チャンネルまたはスレッド内の会話履歴を管理します。
    Phase 1ではインメモリで管理されます。
    """

    model_config = ConfigDict()

    channel_id: str
    thread_ts: str | None = None
    messages: list[SlackMessage] = Field(default_factory=list)
    last_updated: datetime

    @field_serializer("last_updated")
    def serialize_last_updated(self, value: datetime) -> str:
        """last_updatedをISO8601形式の文字列にシリアライズ"""
        return value.isoformat()

    def add_message(self, message: SlackMessage) -> None:
        """メッセージを追加し、最終更新日時を更新

        Args:
            message: 追加するSlackMessageオブジェクト
        """
        self.messages.append(message)
        self.last_updated = datetime.now()

    def get_recent_messages(self, limit: int) -> list[SlackMessage]:
        """直近のlimit件のメッセージを取得

        Args:
            limit: 取得するメッセージ数

        Returns:
            直近のメッセージのリスト（最大limit件）
        """
        return self.messages[-limit:]


class ResponseDecision(BaseModel):
    """応答判定結果モデル

    LLMによる応答判定の結果を保持します。
    """

    should_respond: bool
    reason: str
    confidence: float
    suggested_delay_minutes: int | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """confidenceフィールドのバリデーション

        confidenceは0.0から1.0の範囲内である必要があります。

        Args:
            v: バリデーション対象の値

        Returns:
            バリデーション済みの値

        Raises:
            ValueError: 値が範囲外の場合
        """
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class LLMResponse(BaseModel):
    """LLM応答モデル

    LiteLLMからの応答情報を保持します。
    """

    content: str
    model: str
    usage: dict[str, int]
    finish_reason: str
