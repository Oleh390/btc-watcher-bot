
import asyncio
import json
import os
import websockets
from decimal import Decimal
from dotenv import load_dotenv
import requests

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_USER_ID")

async def fetch_order_book():
    uri = "wss://stream.binance.com:9443/ws/btcusdt@depth"
    async with websockets.connect(uri) as websocket:
        while True:
            data = json.loads(await websocket.recv())

            bids = [(Decimal(p), Decimal(q)) for p, q in data.get("bids") or data.get("b", [])]
            asks = [(Decimal(p), Decimal(q)) for p, q in data.get("asks") or data.get("a", [])]

            message = format_message(bids, asks)
            send_to_telegram(message)
            await asyncio.sleep(5)

def format_message(bids, asks):
    def summarize(levels):
        total_qty = sum(qty for price, qty in levels)
        avg_price = sum(price * qty for price, qty in levels) / total_qty if total_qty else 0
        return avg_price, total_qty

    buy_price, buy_qty = summarize(bids[:10])
    sell_price, sell_qty = summarize(asks[:10])

    return f"""📊 BTC/USDT Order Book
🔵 ±0.2%
📉 Сопротивление: {sell_price:.2f} $ ({sell_qty:.0f} BTC)
📊 Поддержка: {buy_price:.2f} $ ({buy_qty:.0f} BTC)
"""

def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram error:", e)

async def main():
    await fetch_order_book()

if __name__ == "__main__":
    asyncio.run(main())
