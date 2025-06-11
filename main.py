import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
WEBHOOK_ENDPOINT = "/webhook"

@app.route(WEBHOOK_ENDPOINT, methods=["POST"])
def webhook():
    data = request.json
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        print(f"👤 chat_id: {chat_id}")
    return "OK"

@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    print("🚀 Flask сервер запущен")
    app.run(host="0.0.0.0", port=8000)