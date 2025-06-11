import os
import asyncio
import requests
import websockets
from dotenv import load_dotenv
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
        print(f"Telegram error: {e}")

def format_levels(levels):
    return "\n".join([f" ┗ {price:.0f} $ — {volume:.0f} BTC" for price, volume in levels[:3]])

async def analyze_order_book():
    url = "wss://stream.binance.com:9443/ws/btcusdt@depth"
    while True:
        try:
            async with websockets.connect(url) as ws:
                while True:
                    msg = await ws.recv()
                    data = eval(msg)  # quick and dirty parsing
                    bids = sorted([(float(p), float(q)) for p, q in data['b']], reverse=True)
                    asks = sorted([(float(p), float(q)) for p, q in data['a']])
                    best_bid = bids[0][0]
                    best_ask = asks[0][0]
                    mark_price = (best_bid + best_ask) / 2

                    def filter_levels(levels, target, percent):
                        min_p = target * (1 - percent)
                        max_p = target * (1 + percent)
                        return [(p, q) for p, q in levels if min_p <= p <= max_p]

                    ranges = [0.002, 0.02, 0.04, 0.1]
                    messages = []
                    for i, rng in enumerate(ranges):
                        bids_range = filter_levels(bids, mark_price, rng)
                        asks_range = filter_levels(asks, mark_price, rng)

                        top_bids = sorted(bids_range, key=lambda x: x[1], reverse=True)
                        top_asks = sorted(asks_range, key=lambda x: x[1], reverse=True)

                        buy_vol = sum(q for _, q in bids_range)
                        sell_vol = sum(q for _, q in asks_range)
                        dominance = (buy_vol - sell_vol) / max(buy_vol + sell_vol, 1e-9) * 100

                        messages.append(f"""
🔵 Диапазон: ±{int(rng*100)}%
📉 Сопротивление:
{format_levels(top_asks)}
📊 Поддержка:
{format_levels(top_bids)}
""")

                    summary = f"""
📊 BTC/USDT Обзор лимитных ордеров
🟢 Покупатели доминируют: {dominance:+.1f}% (±0.2%)
📈 Поддержка: {top_bids[0][0]:.0f} $ ({top_bids[0][1]:.0f} BTC)
📉 Сопротивление: {top_asks[0][0]:.0f} $ ({top_asks[0][1]:.0f} BTC)

🧭 Сигнал: {"Импульс вверх" if dominance > 25 else "Нейтрально" if -25 < dominance < 25 else "Импульс вниз"}
""" + "\n".join(messages)

                    send_telegram_message(summary)
                    await asyncio.sleep(30)

        except Exception as e:
            print("WebSocket error:", e)
            await asyncio.sleep(5)

@app.route("/")
def home():
    return "CryptoVolumeWatcher is online!"

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(analyze_order_book())
    app.run(host="0.0.0.0", port=8000)
