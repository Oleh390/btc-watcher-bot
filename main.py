
import websocket
import json
import threading
import time
import requests

TELEGRAM_BOT_TOKEN = '7830848319:AAHjRmoCT_1u8ufoIqWDYqi8aT1oFya_Lvs'
TELEGRAM_USER_ID = '437873124'
SYMBOL = 'btcusdt'
DEPTH_LEVELS = [0.002, 0.02, 0.04, 0.1]
CHECK_INTERVAL = 1.0  # проверка каждую секунду
MIN_NOTIONAL = 500_000

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_USER_ID,
        "text": text
    }
    try:
        requests.post(url, json=data)
    except Exception as e:
        print("Ошибка Telegram:", e)

def fetch_order_book():
    url = f"https://api.binance.com/api/v3/depth?symbol={SYMBOL.upper()}&limit=1000"
    try:
        response = requests.get(url, timeout=5)
        return response.json()
    except:
        return None

def fetch_price():
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL.upper()}"
    try:
        response = requests.get(url, timeout=5)
        return float(response.json()["price"])
    except:
        return None

def analyze_depth():
    while True:
        time.sleep(CHECK_INTERVAL)
        price = fetch_price()
        order_book = fetch_order_book()
        if price is None or order_book is None:
            continue

        message = f"📊 BTC/USDT Order Book

"
        for level in DEPTH_LEVELS:
            low = price * (1 - level)
            high = price * (1 + level)

            buy_volume = sum(float(q) * float(p) for p, q in order_book["bids"] if low <= float(p) <= high)
            sell_volume = sum(float(q) * float(p) for p, q in order_book["asks"] if low <= float(p) <= high)
            delta = buy_volume - sell_volume
            total = buy_volume + sell_volume
            if total == 0:
                dominance = 0
            else:
                dominance = abs(delta) / total * 100

            side = "🟢 Покупатели" if delta > 0 else "🔴 Продавцы"
            message += f"🔹 Плотность ±{int(level*100)}%
"
            message += f"{side} доминируют на {dominance:.1f}%
"
            message += f"Buy: {buy_volume:,.0f} $ | Sell: {sell_volume:,.0f} $

"

        if buy_volume >= MIN_NOTIONAL or sell_volume >= MIN_NOTIONAL:
            send_telegram_message(message)

def check_manual_commands():
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            if offset:
                url += f"?offset={offset}"
            updates = requests.get(url).json()
            for result in updates["result"]:
                offset = result["update_id"] + 1
                if "message" in result and result["message"].get("text") == "/depth":
                    analyze_once()
        except:
            time.sleep(1)

def analyze_once():
    price = fetch_price()
    order_book = fetch_order_book()
    if price is None or order_book is None:
        return

    message = f"📊 BTC/USDT Order Book (по запросу)

"
    for level in DEPTH_LEVELS:
        low = price * (1 - level)
        high = price * (1 + level)

        buy_volume = sum(float(q) * float(p) for p, q in order_book["bids"] if low <= float(p) <= high)
        sell_volume = sum(float(q) * float(p) for p, q in order_book["asks"] if low <= float(p) <= high)
        delta = buy_volume - sell_volume
        total = buy_volume + sell_volume
        if total == 0:
            dominance = 0
        else:
            dominance = abs(delta) / total * 100

        side = "🟢 Покупатели" if delta > 0 else "🔴 Продавцы"
        message += f"🔹 Плотность ±{int(level*100)}%
"
        message += f"{side} доминируют на {dominance:.1f}%
"
        message += f"Buy: {buy_volume:,.0f} $ | Sell: {sell_volume:,.0f} $

"

    send_telegram_message(message)

if __name__ == "__main__":
    threading.Thread(target=analyze_depth, daemon=True).start()
    threading.Thread(target=check_manual_commands, daemon=True).start()
    while True:
        time.sleep(10)
