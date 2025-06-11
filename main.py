import os
import asyncio
import websockets
from dotenv import load_dotenv
import requests
from flask import Flask

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = os.getenv("TELEGRAM_USER_ID")

app = Flask(__name__)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": USER_ID, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

@app.route("/")
def home():
    return "CryptoVolumeWatcher is running"

if __name__ == "__main__":
    send_telegram_message("✅ Бот успешно запущен на Railway!")
    app.run(host="0.0.0.0", port=8000)
