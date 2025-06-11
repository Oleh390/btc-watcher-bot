
import os
import json
import asyncio
import websockets
from flask import Flask

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_USER_ID")

app = Flask(__name__)

@app.route("/")
def home():
    return "📡 Flask сервер запущен. Жду сообщения..."

async def connect_to_binance():
    url = "wss://stream.binance.com:9443/ws/btcusdt@depth"
    async with websockets.connect(url) as ws:
        print("✅ WebSocket подключен")
        while True:
            try:
                data = await ws.recv()
                print("📥 Получены данные от Binance")
                json_data = json.loads(data)
                bids = json_data.get("b", [])
                asks = json_data.get("a", [])
                if not bids or not asks:
                    print("⚠️ Нет данных bid/ask")
                else:
                    print("✅ Данные bids/asks получены")
            except Exception as e:
                print(f"❌ Ошибка при получении данных: {e}")
                await asyncio.sleep(2)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(connect_to_binance())
    app.run(host="0.0.0.0", port=8000)
