import os
from decimal import Decimal
from binance.client import Client
from telegram import Bot
from telegram.constants import ParseMode
import asyncio
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_USER_ID")

PAIR = "BTCUSDT"
DEPTH_LIMIT = 1000

# Проценты диапазонов для анализа
RANGES = [0.002, 0.004, 0.02, 0.04, 0.1]
RANGE_LABELS = ["±0.2%", "±0.4%", "±2%", "±4%", "±10%"]

client = Client()

def get_order_book(symbol=PAIR, limit=DEPTH_LIMIT):
    order_book = client.get_order_book(symbol=symbol, limit=limit)
    bids = [(Decimal(price), Decimal(amount)) for price, amount, *_ in order_book["bids"]]
    asks = [(Decimal(price), Decimal(amount)) for price, amount, *_ in order_book["asks"]]
    return bids, asks

def aggregate_levels(levels, lower, upper, reverse=False):
    filtered = [l for l in levels if lower <= l[0] <= upper]
    if not filtered:
        return 0, Decimal(0), 0
    if reverse:
        level = max(filtered, key=lambda x: x[0])
    else:
        level = min(filtered, key=lambda x: x[0])
    volume = sum(a for _, a in filtered)
    count = len(filtered)
    return float(level[0]), float(volume), count

def analyze_order_book(bids, asks, price, rng):
    lower = price * (1 - rng)
    upper = price * (1 + rng)
    # Покупки и продажи отдельно в пределах диапазона
    bids_in = [b for b in bids if lower <= b[0] < price]
    asks_in = [a for a in asks if price < a[0] <= upper]
    bid_vol = sum(a for _, a in bids_in)
    ask_vol = sum(a for _, a in asks_in)
    bid_val = sum(p * a for p, a in bids_in)
    ask_val = sum(p * a for p, a in asks_in)
    bid_count = len(bids_in)
    ask_count = len(asks_in)
    support = max(bids_in, key=lambda x: x[0], default=(0, 0))
    resistance = min(asks_in, key=lambda x: x[0], default=(0, 0))
    dom_side = "Покупатели" if bid_vol > ask_vol else "Продавцы"
    dom_percent = abs(int(100 * (bid_vol - ask_vol) / (bid_vol + ask_vol))) if (bid_vol + ask_vol) else 0
    return {
        "support": support,
        "resistance": resistance,
        "bid_vol": bid_vol,
        "ask_vol": ask_vol,
        "bid_val": bid_val,
        "ask_val": ask_val,
        "bid_count": bid_count,
        "ask_count": ask_count,
        "lower": lower,
        "upper": upper,
        "dom_side": dom_side,
        "dom_percent": dom_percent
    }

def format_value(val, d=2):
    if val == 0:
        return "—"
    return f"{val:,.{d}f}".replace(",", " ")

async def send_signal():
    bids, asks = get_order_book()
    price = float(asks[0][0] + bids[0][0]) / 2
    lines = [f"📊 BTC/USDT Order Book\n"]

    all_stats = []

    for rng, label in zip(RANGES, RANGE_LABELS):
        stats = analyze_order_book(bids, asks, price, rng)
        # Формат
        lines.append(
            f"\n🔵 {label}\n"
            f"📉 Сопротивление: {format_value(stats['resistance'][0])} $ ({format_value(stats['resistance'][1])} BTC)"
            f"\n📊 Поддержка: {format_value(stats['support'][0])} $ ({format_value(stats['support'][1])} BTC)"
            f"\n📈 Диапазон: {format_value(stats['lower'])} — {format_value(stats['upper'])}"
            f"\n🟥 ask уровней: {stats['ask_count']} | 🟩 bid уровней: {stats['bid_count']}"
            f"\n💰 Объём: 🔻 {format_value(stats['ask_vol'])} BTC / ${format_value(stats['ask_val'], 0)} | "
            f"🔺 {format_value(stats['bid_vol'])} BTC / ${format_value(stats['bid_val'], 0)}"
            f"\n{'🟢' if stats['dom_side']=='Покупатели' else '🔴'} {stats['dom_side']} доминируют на {stats['dom_percent']}%"
        )
        all_stats.append(stats)

    # Формируем торговую идею (пример для лонга)
    idea = all_stats[0]  # ±0.2%
    if idea['dom_side'] == 'Покупатели' and idea['support'][0] > 0:
        scenario = f"Лонг от поддержки {format_value(idea['support'][0]-25, 0)}–{format_value(idea['support'][0], 0)} $"
        stop_loss = f"Ниже поддержки → {format_value(idea['support'][0]-50, 0)} $"
        target = f"{format_value(idea['support'][0]+50, 0)}–{format_value(idea['support'][0]+100, 0)} $ (захват ликвидности)"
        filter_text = "Подтверждение объёмом / свечой 1–5м"
        lines.append("\n📌 💡 <b>Торговая идея:</b>")
        lines.append(
            "<pre>Параметр         | Значение\n"
            "------------------|-------------------------------\n"
            f"✅ Сценарий       | {scenario}\n"
            f"⛔️ Стоп-лосс      | {stop_loss}\n"
            f"🎯 Цель           | {target}\n"
            f"🔎 Доп. фильтр    | {filter_text}\n"
            "</pre>"
        )

    await Bot(token=TOKEN).send_message(
        chat_id=CHAT_ID,
        text="\n".join(lines),
        parse_mode=ParseMode.HTML
    )

if __name__ == "__main__":
    asyncio.run(send_signal())
