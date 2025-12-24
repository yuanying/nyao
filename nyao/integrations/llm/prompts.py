"""プロンプト管理

応答判定と応答生成のプロンプトテンプレートとPromptManagerクラスを提供します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nyao.config.settings import Settings
    from nyao.core.models import ConversationContext, SlackMessage


# 応答判定プロンプトテンプレート
SHOULD_RESPOND_PROMPT_TEMPLATE = """あなたはSlackボット「Nyao」の応答判定システムです。
以下のメッセージに対して、ボットが応答すべきかどうかを判定してください。

## ボットのペルソナ
{persona}

## メッセージ情報
- チャンネル: {channel_id}
- 投稿者: {user_name}
- メッセージ: {text}
- 経過時間: {elapsed_seconds}秒
- リアクション数: {reaction_count}
- 返信数: {reply_count}

## 判定基準
応答すべき場合:
- 質問や相談が含まれている
- 共有や感想が述べられていて、反応がない
- 挨拶や呼びかけに対して誰も反応していない

応答すべきでない場合:
- 既に他のユーザーが反応している（リアクションや返信がある）
- 自動投稿やBot投稿である
- プライベートな内容や通知メッセージ
- 独り言や単なるメモ書き

## 出力形式
以下のJSON形式で回答してください:
{{
    "should_respond": true/false,
    "reason": "判定理由（50文字以内）",
    "confidence": 0.0-1.0の確信度,
    "suggested_delay_minutes": null
}}
"""

# 応答生成プロンプトテンプレート
RESPONSE_GENERATION_PROMPT_TEMPLATE = """あなたは「Nyao」という名前のSlackボットです。

## ペルソナ
{persona}

## 返信ガイドライン
- カジュアルな口調で、友達に話しかけるように返信する
- 1〜3文程度の短い返信を心がける
- 絵文字を適度に使用する
- 相手の気持ちに寄り添う

## 会話コンテキスト
{context}

## 返信対象のメッセージ
投稿者: {user_name}
メッセージ: {text}

上記のメッセージに対して、友達として自然に返信してください。
"""


class PromptManager:
    """プロンプト管理クラス

    応答判定と応答生成のプロンプトを構築・管理する。
    """

    def __init__(self, persona: str) -> None:
        """初期化

        Args:
            persona: ボットのペルソナ設定
        """
        self.persona = persona

    def build_should_respond_prompt(
        self,
        message: SlackMessage,
        elapsed_seconds: int,
        reaction_count: int,
        reply_count: int,
    ) -> list[dict[str, str]]:
        """応答判定用プロンプトを構築

        Args:
            message: 対象のSlackメッセージ
            elapsed_seconds: メッセージ投稿からの経過秒数
            reaction_count: リアクション数
            reply_count: 返信数

        Returns:
            OpenAI形式のメッセージリスト
        """
        content = SHOULD_RESPOND_PROMPT_TEMPLATE.format(
            persona=self.persona,
            channel_id=message.channel_id,
            user_name=message.user_name,
            text=message.text,
            elapsed_seconds=elapsed_seconds,
            reaction_count=reaction_count,
            reply_count=reply_count,
        )

        return [
            {"role": "system", "content": content},
        ]

    def build_response_generation_prompt(
        self,
        message: SlackMessage,
        context: ConversationContext | None = None,
    ) -> list[dict[str, str]]:
        """応答生成用プロンプトを構築

        Args:
            message: 返信対象のSlackメッセージ
            context: 会話コンテキスト（オプション）

        Returns:
            OpenAI形式のメッセージリスト
        """
        # コンテキストをテキスト形式に変換
        if context is not None and context.messages:
            context_lines = []
            for msg in context.messages:
                context_lines.append(f"- {msg.user_name}: {msg.text}")
            context_text = "\n".join(context_lines)
        else:
            context_text = "（過去の会話履歴はありません）"

        content = RESPONSE_GENERATION_PROMPT_TEMPLATE.format(
            persona=self.persona,
            context=context_text,
            user_name=message.user_name,
            text=message.text,
        )

        return [
            {"role": "system", "content": content},
        ]

    @classmethod
    def from_settings(cls, settings: Settings) -> PromptManager:
        """設定からPromptManagerを生成するファクトリメソッド

        Args:
            settings: アプリケーション設定

        Returns:
            設定に基づいて初期化されたPromptManager
        """
        return cls(persona=settings.bot.persona)
