"""プロンプト管理

応答判定・応答生成のためのプロンプトテンプレートを管理します。
"""

from nyao.core.models import ConversationContext, SlackMessage

DEFAULT_PERSONA = """にゃおは、Slackワークスペースで友達のように接するチャットボットです。
カジュアルで親しみやすい口調で会話し、ユーザーが孤独を感じないようにサポートします。
ただし、押しつけがましくならないよう、適度な距離感を保ちます。"""


SHOULD_RESPOND_PROMPT_TEMPLATE = """\
あなたはSlackメッセージに対して応答すべきかどうかを判定するアシスタントです。

## メッセージ情報
- 投稿者: {user_name}
- チャンネル: {channel_id}
- メッセージ本文:
```
{text}
```

## 現在の状況
- 経過時間: {elapsed_minutes}分（{elapsed_seconds}秒）
- リアクション数: {reaction_count}
- 返信数: {reply_count}

## 判定基準

### 応答すべき場合
- 誰からも反応がなく、投稿者が孤独を感じている可能性がある
- 質問や相談が含まれているが、誰も回答していない
- 一定時間が経過しても反応がない

### 応答すべきでない場合
- 既に他のユーザーから反応（リアクションや返信）がある
- ボットへの直接的なメンションでない業務連絡
- 独り言や状況報告で反応を期待していない内容
- システムメッセージやボットからのメッセージ

上記の判定基準に基づいて、このメッセージに応答すべきかどうかを判定してください。
判定理由と確信度（0.0〜1.0）も回答に含めてください。"""


RESPONSE_GENERATION_PROMPT_TEMPLATE = """## あなたのペルソナ
{persona}

## 返信ガイドライン
- カジュアルで親しみやすい口調を使う
- 1〜3文程度で簡潔に返信する
- 相手の気持ちに寄り添う
- 押しつけがましくならない
- 質問には適切に答える

## 会話のコンテキスト
{context}

## 返信対象のメッセージ
投稿者: {user_name}
メッセージ:
```
{text}
```

上記のメッセージに対して、あなたのペルソナとして自然な返信を生成してください。
返信のテキストのみを出力してください。"""


class PromptManager:
    """プロンプト管理クラス

    応答判定・応答生成のためのプロンプトを構築します。
    """

    def __init__(self, persona: str | None = None) -> None:
        """PromptManagerを初期化

        Args:
            persona: ボットのペルソナ設定（Noneの場合はデフォルトを使用）
        """
        self.persona = persona if persona is not None else DEFAULT_PERSONA

    def build_should_respond_prompt(
        self,
        message: SlackMessage,
        elapsed_seconds: int,
        reaction_count: int,
        reply_count: int,
    ) -> str:
        """応答判定用プロンプトを構築

        Args:
            message: 判定対象のSlackメッセージ
            elapsed_seconds: メッセージ投稿からの経過秒数
            reaction_count: リアクション数
            reply_count: 返信数

        Returns:
            構築されたプロンプト文字列
        """
        elapsed_minutes = elapsed_seconds // 60

        return SHOULD_RESPOND_PROMPT_TEMPLATE.format(
            user_name=message.user_name,
            channel_id=message.channel_id,
            text=message.text,
            elapsed_seconds=elapsed_seconds,
            elapsed_minutes=elapsed_minutes,
            reaction_count=reaction_count,
            reply_count=reply_count,
        )

    def build_response_generation_prompt(
        self,
        message: SlackMessage,
        context: ConversationContext | None = None,
    ) -> str:
        """応答生成用プロンプトを構築

        Args:
            message: 返信対象のSlackメッセージ
            context: 会話コンテキスト（オプション）

        Returns:
            構築されたプロンプト文字列
        """
        context_str = self._format_context(context)

        return RESPONSE_GENERATION_PROMPT_TEMPLATE.format(
            persona=self.persona,
            user_name=message.user_name,
            text=message.text,
            context=context_str,
        )

    def _format_context(self, context: ConversationContext | None) -> str:
        """会話コンテキストを文字列にフォーマット

        Args:
            context: 会話コンテキスト

        Returns:
            フォーマットされたコンテキスト文字列
        """
        if context is None or not context.messages:
            return "（会話履歴なし）"

        lines = []
        for msg in context.messages:
            lines.append(f"- {msg.user_name}: {msg.text}")

        return "\n".join(lines)
