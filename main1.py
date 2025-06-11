import asyncio
import json
import os
import requests
import websockets

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_USER_ID")

async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

async def main():
    uri = "wss://stream.binance.com:9443/ws/btcusdt@depth"
    async with websockets.connect(uri) as websocket:
        print("🟢 Подключено к WebSocket")
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                bids = data.get("b", [])
                asks = data.get("a", [])
                if bids and asks:
                    text = f"Обновление стакана:\n🔽 Bid: {bids[0]}\n🔼 Ask: {asks[0]}"
                    print(text)
                    await send_telegram_message(text)
            except Exception as e:
                print(f"Ошибка: {e}")
                await asyncio.sleep(1)

asyncio.run(main())