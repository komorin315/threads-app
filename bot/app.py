import os
import json
from openai import OpenAI
from notion_client import Client
from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage

app = Flask(__name__)

# 環境変数から取得（後で設定）
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
NOTION_API_KEY = os.environ.get('NOTION_API_KEY')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# 初期化
openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion = Client(auth=NOTION_API_KEY)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def categorize_with_ai(message_text):
    """OpenAIでメッセージをカテゴリ分け"""
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
    return json.loads(content)

def save_to_notion(category, title, content):
    """Notionに保存"""
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

@app.route("/webhook", methods=['POST'])
def webhook():
    """LINE Webhookエンドポイント"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400

    return jsonify({'status': 'ok'}), 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """LINEメッセージを処理"""
    message_text = event.message.text

    try:
        # OpenAIでカテゴリ分け
        result = categorize_with_ai(message_text)

        # Notionに保存
        save_to_notion(
            category=result['category'],
            title=result['title'],
            content=message_text
        )

        # LINE返信（成功）
        reply_text = f"✅ 保存しました！\nカテゴリ: {result['category']}\nタイトル: {result['title']}"

    except Exception as e:
        reply_text = f"❌ エラーが発生しました: {str(e)}"

    line_bot_api.reply_message(
        event.reply_token,
        TextMessage(text=reply_text)
    )

if __name__ == "__main__":
    # ローカルテスト用
    app.run(host='0.0.0.0', port=5000, debug=True)
