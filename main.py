import asyncio
import json
import math
import os
import websockets
import requests
from datetime import datetime
from decimal import Decimal

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
SYMBOL = "btcusdt"

DEPTH_LIMIT = 1000
PRICE_LEVELS = [0.002, 0.004, 0.02, 0.04]  # ±0.2%, ±0.4%, ±2%, ±4%

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def format_number(n):
    return f"{n:,.2f}".replace(",", " ")

def get_aggregated_volume(levels, price, is_bid, depth):
    total_volume = 0
    best_price = 0
    filtered = []

    for p_str, qty_str in levels:
        p = float(p_str)
        if is_bid and price * (1 - depth) <= p <= price:
            filtered.append((p, float(qty_str)))
        elif not is_bid and price <= p <= price * (1 + depth):
            filtered.append((p, float(qty_str)))

    if filtered:
        best_price, best_qty = max(filtered, key=lambda x: x[1]) if not is_bid else min(filtered, key=lambda x: x[1])
        total_volume = sum(q for _, q in filtered)
    return best_price, total_volume, filtered

def get_depth_stats(levels, price, depth, is_bid):
    min_price = price * (1 - depth)
    max_price = price * (1 + depth)
    levels_filtered = [(float(p), float(q)) for p, q in levels if min_price <= float(p) <= max_price]
    if not levels_filtered:
        return 0, 0, 0, 0.0

    total_btc = sum(q for _, q in levels_filtered)
    total_usdt = sum(p * q for p, q in levels_filtered)
    level_count = len(levels_filtered)
    if is_bid:
        support_price = max(levels_filtered, key=lambda x: x[1])[0]
        support_qty = max(levels_filtered, key=lambda x: x[1])[1]
        return support_price, support_qty, level_count, total_btc, total_usdt
    else:
        resist_price = min(levels_filtered, key=lambda x: x[1])[0]
        resist_qty = min(levels_filtered, key=lambda x: x[1])[1]
        return resist_price, resist_qty, level_count, total_btc, total_usdt

async def main():
    url = f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth@100ms"
    async with websockets.connect(url) as ws:
        while True:
            response = await ws.recv()
            data = json.loads(response)

            bids = data.get("bids", [])[:DEPTH_LIMIT]
            asks = data.get("asks", [])[:DEPTH_LIMIT]

            if not bids or not asks:
                continue

            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            mark_price = (best_bid + best_ask) / 2

            message = f"<b>📊 BTC/USDT Order Book</b>\n"
            idea_support = ""
            idea_resist = ""

            for depth in PRICE_LEVELS:
                resist_price, resist_qty, ask_levels, ask_btc, ask_usdt = get_depth_stats(asks, mark_price, depth, is_bid=False)
                support_price, support_qty, bid_levels, bid_btc, bid_usdt = get_depth_stats(bids, mark_price, depth, is_bid=True)

                if resist_price == 0 or support_price == 0:
                    continue

                total = ask_btc + bid_btc
                dominance = (bid_btc - ask_btc) / total * 100 if total > 0 else 0
                dom_str = f"🟢 Покупатели доминируют на {round(abs(dominance))}%"
                if dominance < 0:
                    dom_str = f"🔴 Продавцы доминируют на {round(abs(dominance))}%"

                depth_percent = f"{int(depth * 1000)/10:.1f}%"

                message += (
                    f"\n🔵 ±{depth_percent}\n"
                    f"📉 Сопротивление: {format_number(resist_price)} $ ({int(resist_qty)} BTC)\n"
                    f"📊 Поддержка: {format_number(support_price)} $ ({int(support_qty)} BTC)\n"
                    f"📈 Диапазон: {format_number(mark_price * (1 - depth))} — {format_number(mark_price * (1 + depth))}\n"
                    f"🟥 ask уровней: {ask_levels} | 🟩 bid уровней: {bid_levels}\n"
                    f"💰 Объём: 🔻 {format_number(ask_btc)} BTC / ${format_number(ask_usdt)} | 🔺 {format_number(bid_btc)} BTC / ${format_number(bid_usdt)}\n"
                    f"{dom_str}\n"
                )

                # Для идеи используем ±0.2%
                if depth == 0.002:
                    idea_support = f"{format_number(support_price - 25)}–{format_number(support_price)} $"
                    idea_resist = f"{format_number(resist_price + 50)}–{format_number(resist_price + 100)} $"
                    stop_loss = f"{format_number(support_price - 500)} $"

            message += "\n🧭 <b>Сводка:</b>\nОбъём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост.\n"

            message += (
                "\n📌 💡 <b>Торговая идея:</b>\n"
                "<pre>Параметр         | Значение\n"
                "------------------|-------------------------------\n"
                f"<b>✅ Сценарий       | Лонг от поддержки {idea_support}</b>\n"
                f"⛔ Стоп-лосс      | Ниже поддержки → {stop_loss}\n"
                f"<b>🎯 Цель           | {idea_resist} (захват ликвидности)</b>\n"
                "🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
                "</pre>"
            )

            send_telegram_message(message)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
