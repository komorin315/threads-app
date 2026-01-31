import os
import json
import traceback
from openai import OpenAI
from notion_client import Client
from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)

# 環境変数から取得
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
NOTION_API_KEY = os.environ.get('NOTION_API_KEY')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# 起動時に環境変数をチェック
print("=== 環境変数チェック ===")
print(f"OPENAI_API_KEY: {'設定済み' if OPENAI_API_KEY else '未設定！'}")
print(f"NOTION_API_KEY: {'設定済み' if NOTION_API_KEY else '未設定！'}")
print(f"NOTION_DATABASE_ID: {'設定済み' if NOTION_DATABASE_ID else '未設定！'}")
print(f"LINE_CHANNEL_ACCESS_TOKEN: {'設定済み' if LINE_CHANNEL_ACCESS_TOKEN else '未設定！'}")
print(f"LINE_CHANNEL_SECRET: {'設定済み' if LINE_CHANNEL_SECRET else '未設定！'}")
print("========================")

# 初期化
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
notion = Client(auth=NOTION_API_KEY) if NOTION_API_KEY else None
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN) if LINE_CHANNEL_ACCESS_TOKEN else None
handler = WebhookHandler(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None

def categorize_with_ai(message_text):
    """OpenAIでメッセージをカテゴリ分け"""
    print(f"[AI] カテゴリ分け開始: {message_text[:50]}...")
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""以下のメモを分析して、カテゴリとタイトルを決めてください。

カテゴリは以下から選択：
- 仕事
- プライベート
- アイデア
- 買い物
- TODO
- その他

必ずJSON形式で返してください：
{{"category": "カテゴリ名", "title": "簡潔なタイトル（20文字以内）"}}

メモ内容：
{message_text}"""
        }],
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    print(f"[AI] 結果: {content}")
    return json.loads(content)

def save_to_notion(category, title, content):
    """Notionに保存"""
    print(f"[Notion] 保存開始: {title}")
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "名前": {
                "title": [{"text": {"content": title}}]
            },
            "カテゴリ": {
                "select": {"name": category}
            },
            "メモ内容": {
                "rich_text": [{"text": {"content": content}}]
            }
        }
    )
    print(f"[Notion] 保存完了")

@app.route("/", methods=['GET'])
def health():
    """ヘルスチェック"""
    return jsonify({'status': 'ok', 'message': 'Bot is running'}), 200

@app.route("/webhook", methods=['POST'])
def webhook():
    """LINE Webhookエンドポイント"""
    print("[Webhook] リクエスト受信")

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    print(f"[Webhook] Body: {body[:200]}...")

    if not handler:
        print("[Webhook] エラー: handler未初期化")
        return jsonify({'error': 'handler not initialized'}), 500

    try:
        handler.handle(body, signature)
        print("[Webhook] handler.handle完了")
    except InvalidSignatureError:
        print("[Webhook] エラー: 署名が無効")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        print(f"[Webhook] エラー: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

    return jsonify({'status': 'ok'}), 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """LINEメッセージを処理"""
    print("[Handler] メッセージ受信")
    message_text = event.message.text
    print(f"[Handler] テキスト: {message_text}")

    try:
        # OpenAIでカテゴリ分け
        result = categorize_with_ai(message_text)
        print(f"[Handler] AI結果: {result}")

        # Notionに保存
        save_to_notion(
            category=result['category'],
            title=result['title'],
            content=message_text
        )

        # LINE返信（成功）
        reply_text = f"✅ 保存しました！\nカテゴリ: {result['category']}\nタイトル: {result['title']}"
        print(f"[Handler] 返信: {reply_text}")

    except Exception as e:
        print(f"[Handler] エラー発生: {e}")
        print(traceback.format_exc())
        reply_text = f"❌ エラーが発生しました: {str(e)}"

    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        print("[Handler] 返信送信完了")
    except Exception as e:
        print(f"[Handler] 返信送信エラー: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    print(f"サーバー起動: ポート {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
