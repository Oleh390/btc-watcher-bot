
import json
import requests
import websocket
import threading
import time

TELEGRAM_BOT_TOKEN = '7830848319:AAHjRmoCT_1u8ufoIqWDYqi8aT1oFya_Lvs'
TELEGRAM_USER_ID = '437873124'
SYMBOL = 'btcusdt'
AGGREGATION_INTERVAL = 0.3
MIN_TOTAL_VOLUME = 250_000

lock = threading.Lock()
buffer = []

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Ошибка отправки Telegram:", e)

def aggregate_order_book():
    global buffer
    while True:
        time.sleep(AGGREGATION_INTERVAL)
        with lock:
            local_buffer = buffer
            buffer = []

        if not local_buffer:
            continue

        buy_volume = sum(level['q'] * level['p'] for level in local_buffer if level['side'] == 'buy')
        sell_volume = sum(level['q'] * level['p'] for level in local_buffer if level['side'] == 'sell')

        total_volume = buy_volume + sell_volume
        if total_volume < MIN_TOTAL_VOLUME:
            continue

        dominance = buy_volume / total_volume if total_volume else 0
        side = "🟢 Покупатели" if dominance > 0.5 else "🔴 Продавцы"
        percent = round(abs(dominance - 0.5) * 200)

        diff = buy_volume - sell_volume
        sign = "+" if diff >= 0 else "-"
        msg = (
            f"📊 BTC/USDT Order Book

"
            f"{side} доминируют на {percent}%
"
            f"🔼 Buy Volume: {buy_volume:,.0f} USDT
"
            f"🔽 Sell Volume: {sell_volume:,.0f} USDT
"
            f"📈 Разница: {sign}{abs(diff):,.0f} USDT
"
        )
        send_telegram_message(msg)
        print(msg)

def on_message(ws, message):
    try:
        data = json.loads(message)
        updates = []
        for side, levels in [('buy', data.get('b', [])), ('sell', data.get('a', []))]:
            for price, qty in levels:
                updates.append({
                    'side': side,
                    'p': float(price),
                    'q': float(qty)
                })
        with lock:
            buffer.extend(updates)
    except Exception as e:
        print("Ошибка обработки сообщения:", e)

def on_error(ws, error):
    print("Ошибка WebSocket:", error)

def on_close(ws, code, msg):
    print("WebSocket закрыт")

def on_open(ws):
    print("Соединение WebSocket открыто")

if __name__ == "__main__":
    threading.Thread(target=aggregate_order_book, daemon=True).start()
    ws = websocket.WebSocketApp(
        f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth10@100ms",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()
