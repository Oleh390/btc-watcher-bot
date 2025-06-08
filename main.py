import websocket
import json
import threading
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_USER_ID")
SYMBOL = 'btcusdt'
AGGREGATION_WINDOW = 5
DEPTH_PERCENT_RANGE = 0.001  # 0.1%

lock = threading.Lock()
order_book_data = {}

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, json=payload)

def on_message(ws, message):
    global order_book_data
    try:
        data = json.loads(message)
        bids = data['bids']
        asks = data['asks']
        current_price = (float(bids[0][0]) + float(asks[0][0])) / 2
        bid_volume = sum(float(b[1]) for b in bids if abs(float(b[0]) - current_price) / current_price <= DEPTH_PERCENT_RANGE)
        ask_volume = sum(float(a[1]) for a in asks if abs(float(a[0]) - current_price) / current_price <= DEPTH_PERCENT_RANGE)

        total_volume = bid_volume + ask_volume
        dominance = "Баланс"
        percent = 50

        if total_volume > 0:
            percent = int((max(bid_volume, ask_volume) / total_volume) * 100)
            dominance = "покупатели" if bid_volume > ask_volume else "продавцы"

        msg = (
            f"📊 BTC/USDT Order Book\n\n"
            f"{'🟢' if dominance == 'покупатели' else '🔴'} Преобладают {dominance} — {percent}%\n"
            f"🔼 Buy Volume: {bid_volume:.2f} BTC\n"
            f"🔽 Sell Volume: {ask_volume:.2f} BTC\n"
            f"📈 Разница: {bid_volume - ask_volume:.2f} BTC\n\n"
            f"📏 Диапазон: ±{DEPTH_PERCENT_RANGE * 100:.1f}% от цены"
        )
        send_message(msg)
    except Exception as e:
        print("Ошибка:", e)

def on_open(ws):
    payload = {
        "method": "SUBSCRIBE",
        "params": [f"{SYMBOL}@depth10@100ms"],
        "id": 1
    }
    ws.send(json.dumps(payload))
    print("WebSocket открыт")

def on_error(ws, error):
    print("Ошибка WebSocket:", error)

def on_close(ws, *args):
    print("WebSocket закрыт")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        "wss://stream.binance.com:9443/ws",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    threading.Thread(target=ws.run_forever).start()
