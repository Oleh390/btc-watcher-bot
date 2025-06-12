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
    asks_in_range = [(p, q) for p, q in asks if lower < p <= upper]
    bids_in_range = [(p, q) for p, q in bids if lower <= p < upper]
    ask_count = len(asks_in_range)
    bid_count = len(bids_in_range)
    ask_volume = sum(q for p, q in asks_in_range)
    bid_volume = sum(q for p, q in bids_in_range)
    ask_money = sum(p * q for p, q in asks_in_range)
    bid_money = sum(p * q for p, q in bids_in_range)
    support = max(bids_in_range, key=lambda x: x[1], default=(0, 0))  # bid с макс. объемом
    resistance = max(asks_in_range, key=lambda x: x[1], default=(0, 0))  # ask с макс. объемом
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
        "label": f"±{percent}%",
        "percent": percent
    }

def format_num(n, nd=2):
    if n is None: return "—"
    if abs(n) >= 10000:
        return f"{n:,.0f}".replace(",", " ")
    return f"{n:,.{nd}f}"

def choose_best_range(levels):
    # Сначала ищем max объём поддержки (для покупателей), потом max объём сопротивления (для продавцов)
    max_bid = max(levels, key=lambda l: l['bid_volume'])
    max_ask = max(levels, key=lambda l: l['ask_volume'])
    if max_bid["side"] == "Покупатели" and max_bid["bid_volume"] > 0:
        return max_bid, "long"
    elif max_ask["side"] == "Продавцы" and max_ask["ask_volume"] > 0:
        return max_ask, "short"
    else:
        return levels[0], "long"  # fallback

def build_message(levels, mid_price, idea_level, idea_type):
    lines = ["📊 BTC/USDT Order Book\n"]
    for lvl in levels:
        lines.append(
            f"🔵 {lvl['label']}\n"
            f"📉 Сопротивление: {format_num(lvl['resistance'][0])} $ ({format_num(lvl['resistance'][1], 0)} BTC)"
            f"\n📊 Поддержка: {format_num(lvl['support'][0])} $ ({format_num(lvl['support'][1], 0)} BTC)"
            f"\n📈 Диапазон: {format_num(lvl['rng_min'])} — {format_num(lvl['rng_max'])}"
            f"\n🟥 ask уровней: {lvl['ask_count']} | 🟩 bid уровней: {lvl['bid_count']}"
            f"\n💰 Объём: 🔻 {format_num(lvl['ask_volume'], 2)} BTC / ${format_num(lvl['ask_money'], 0)}"
            f" | 🔺 {format_num(lvl['bid_volume'], 2)} BTC / ${format_num(lvl['bid_money'], 0)}"
            f"\n{'🟢'*2 if lvl['side'] == 'Покупатели' else '🔴'*2} {lvl['side']} доминируют на {lvl['dom_pct']}%"
            "\n"
        )

    # Описание торговой идеи:
    reason = ""
    if idea_type == "long":
        reason = (
            f"Бот выбрал диапазон <b>{idea_level['label']}</b>, т.к. здесь максимальный объём на поддержку "
            f"(<b>{format_num(idea_level['bid_volume'], 0)} BTC</b>) и явное доминирование покупателей (<b>{idea_level['dom_pct']}%</b>)."
        )
        entry = f"Лонг от поддержки {format_num(idea_level['support'][0]-25)}–{format_num(idea_level['support'][0])} $"
        sl = f"Ниже поддержки → {format_num(idea_level['support'][0]-50)} $"
        tp = f"{format_num(idea_level['support'][0])}–{format_num(idea_level['support'][0]+550)} $ (захват ликвидности)"
    else:
        reason = (
            f"Бот выбрал диапазон <b>{idea_level['label']}</b>, т.к. здесь максимальный объём на сопротивление "
            f"(<b>{format_num(idea_level['ask_volume'], 0)} BTC</b>) и явное доминирование продавцов (<b>{idea_level['dom_pct']}%</b>)."
        )
        entry = f"Шорт от сопротивления {format_num(idea_level['resistance'][0])}–{format_num(idea_level['resistance'][0]+25)} $"
        sl = f"Выше сопротивления → {format_num(idea_level['resistance'][0]+50)} $"
        tp = f"{format_num(idea_level['resistance'][0]-550)}–{format_num(idea_level['resistance'][0])} $ (захват ликвидности)"

    lines.append(
        f"\n📌 💡 <b>Торговая идея (авто-выбор диапазона)</b>\n"
        f"{reason}\n"
        "<pre>Параметр         | Значение\n"
        "------------------|-------------------------------\n"
        f"✅ Сценарий       | {entry}\n"
        f"⛔️ Стоп-лосс      | {sl}\n"
        f"🎯 Цель           | {tp}\n"
        f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
        "</pre>"
    )
    return "\n".join(lines)

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    bids, asks = await get_order_book()
    mid_price = (asks[0][0] + bids[0][0]) / 2 if asks and bids else 0

    levels = []
    for pct, label in INTERVALS:
        levels.append(calc_levels(bids, asks, mid_price, pct))

    idea_level, idea_type = choose_best_range(levels)
    message = build_message(levels, mid_price, idea_level, idea_type)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode=ParseMode.HTML)

if __name__ == "__main__":
    asyncio.run(main())
