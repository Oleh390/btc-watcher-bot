import asyncio
import os
from decimal import Decimal
from dotenv import load_dotenv
from binance import AsyncClient
from telegram import Bot
from telegram.constants import ParseMode

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_USER_ID")

PAIR = "BTCUSDT"

INTERVALS = [
    (0.2, "±0.2%"),
    (0.4, "±0.4%"),
    (2, "±2%"),
    (4, "±4%"),
]

async def get_order_book():
    async with AsyncClient() as client:
        depth = await client.get_order_book(symbol=PAIR, limit=1000)
        bids = [(float(price), float(amount)) for price, amount in depth["bids"]]
        asks = [(float(price), float(amount)) for price, amount in depth["asks"]]
        return bids, asks

def calc_levels(bids, asks, mid_price, percent):
    lower = mid_price * (1 - percent / 100)
    upper = mid_price * (1 + percent / 100)

    # asks — только цены ВЫШЕ mid_price
    asks_in_range = [(p, q) for p, q in asks if lower < p <= upper]
    bids_in_range = [(p, q) for p, q in bids if lower <= p < upper]

    ask_count = len(asks_in_range)
    bid_count = len(bids_in_range)
    ask_volume = sum(q for p, q in asks_in_range)
    bid_volume = sum(q for p, q in bids_in_range)
    ask_money = sum(p * q for p, q in asks_in_range)
    bid_money = sum(p * q for p, q in bids_in_range)

    # Поддержка: bid с макс. объемом, Сопротивление: ask с макс. объемом
    support = max(bids_in_range, key=lambda x: x[1], default=(0, 0))
    resistance = max(asks_in_range, key=lambda x: x[1], default=(0, 0))

    rng_min = min([p for p, _ in bids_in_range + asks_in_range], default=mid_price)
    rng_max = max([p for p, _ in bids_in_range + asks_in_range], default=mid_price)

    side = "Покупатели" if bid_volume > ask_volume else "Продавцы"
    dom_pct = int(abs(bid_volume - ask_volume) / max(bid_volume + ask_volume, 1e-8) * 100)

    return {
        "support": support,
        "resistance": resistance,
        "bid_count": bid_count,
        "ask_count": ask_count,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "bid_money": bid_money,
        "ask_money": ask_money,
        "rng_min": rng_min,
        "rng_max": rng_max,
        "side": side,
        "dom_pct": dom_pct,
    }

def format_num(n, nd=2):
    if n is None: return "—"
    if abs(n) >= 10000:
        return f"{n:,.0f}".replace(",", " ")
    return f"{n:,.{nd}f}"

def build_message(levels, mid_price):
    lines = ["📊 BTC/USDT Order Book\n"]
    for i, (pct, label) in enumerate(INTERVALS):
        stats = levels[i]
        lines.append(
            f"🔵 {label}\n"
            f"📉 Сопротивление: {format_num(stats['resistance'][0])} $ ({format_num(stats['resistance'][1], 0)} BTC)"
            f"\n📊 Поддержка: {format_num(stats['support'][0])} $ ({format_num(stats['support'][1], 0)} BTC)"
            f"\n📈 Диапазон: {format_num(stats['rng_min'])} — {format_num(stats['rng_max'])}"
            f"\n🟥 ask уровней: {stats['ask_count']} | 🟩 bid уровней: {stats['bid_count']}"
            f"\n💰 Объём: 🔻 {format_num(stats['ask_volume'], 2)} BTC / ${format_num(stats['ask_money'], 0)}"
            f" | 🔺 {format_num(stats['bid_volume'], 2)} BTC / ${format_num(stats['bid_money'], 0)}"
            f"\n🟢 Покупатели доминируют на {stats['dom_pct']}%" if stats["side"] == "Покупатели"
            else f"\n🔴 Продавцы доминируют на {stats['dom_pct']}%"
        )
        lines.append("")  # Пустая строка для разделения

    # Торговая идея — по самой первой поддержке/сопротивлению
    idea = (
        "\n📌 💡 <b>Торговая идея:</b>\n"
        "<pre>Параметр         | Значение\n"
        "------------------|-------------------------------\n"
        f"✅ Сценарий       | Лонг от поддержки {format_num(levels[0]['support'][0]-25)}–{format_num(levels[0]['support'][0])} $\n"
        f"⛔️ Стоп-лосс      | Ниже поддержки → {format_num(levels[0]['support'][0]-50)} $\n"
        f"🎯 Цель           | {format_num(levels[0]['support'][0])}–{format_num(levels[0]['support'][0]+550)} $ (захват ликвидности)\n"
        f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
        "</pre>"
    )
    lines.append(idea)
    return "\n".join(lines)

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    bids, asks = await get_order_book()
    mid_price = (asks[0][0] + bids[0][0]) / 2

    levels = []
    for pct, _ in INTERVALS:
        stats = calc_levels(bids, asks, mid_price, pct)
        levels.append(stats)

    message = build_message(levels, mid_price)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode=ParseMode.HTML)

if __name__ == "__main__":
    asyncio.run(main())
