
import asyncio
import json
import websockets
import os
import requests
from decimal import Decimal, ROUND_HALF_UP

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")

symbol = "BTCUSDT"
depth_levels = {
    "±0.2%": 0.002,
    "±2%": 0.02,
    "±4%": 0.04,
    "±10%": 0.10,
}

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_USER_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=data)

def calculate_levels(bids, asks, mark_price, range_percent):
    upper = mark_price * (1 + range_percent)
    lower = mark_price * (1 - range_percent)
    buy_total = sell_total = Decimal('0')
    support_level = resistance_level = None
    max_bid = max_ask = Decimal('0')
    sup_price = res_price = None

    for price, qty in bids:
        if price >= lower:
            buy_total += qty
            if qty > max_bid:
                max_bid = qty
                sup_price = price

    for price, qty in asks:
        if price <= upper:
            sell_total += qty
            if qty > max_ask:
                max_ask = qty
                res_price = price

    dominance = ((buy_total - sell_total) / (buy_total + sell_total + 1e-6)) * 100
    return {
        "buy": buy_total,
        "sell": sell_total,
        "dominance": dominance,
        "support": (sup_price, max_bid),
        "resistance": (res_price, max_ask)
    }

async def main():
    url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@depth@100ms"
    mark_price_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    async with websockets.connect(url) as ws:
        while True:
            data = json.loads(await ws.recv())
            bids = [(Decimal(p), Decimal(q)) for p, q in data['bids']]
            asks = [(Decimal(p), Decimal(q)) for p, q in data['asks']]
            try:
                mark_price = Decimal(requests.get(mark_price_url).json()['price'])
            except:
                continue

            lines = ["📊 *BTC/USDT Order Book*\n"]
            for label, percent in depth_levels.items():
                result = calculate_levels(bids, asks, mark_price, percent)
                res_price, res_qty = result['resistance']
                sup_price, sup_qty = result['support']
                side = "🟢 Покупатели" if result['dominance'] > 0 else "🔴 Продавцы"
                dom = abs(Decimal(result['dominance'])).quantize(Decimal('1.0'), rounding=ROUND_HALF_UP)
                lines.append(
                    f"🔵 *{label}*\n"
                    f"📉 Сопротивление: {res_price:.0f} $ ({res_qty:.0f} BTC)\n"
                    f"📊 Поддержка: {sup_price:.0f} $ ({sup_qty:.0f} BTC)\n"
                    f"{side} доминируют на *{dom}%*\n"
                )
            send_telegram_message("\n".join(lines))
            await asyncio.sleep(60)

asyncio.run(main())
