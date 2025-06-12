import asyncio
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = int(os.getenv('TELEGRAM_USER_ID'))

SYMBOL = 'BTCUSDT'
DEPTH_LEVELS = [
    ("±0.2%", 0.2),
    ("±0.4%", 0.4),
    ("±2%", 2),
    ("±4%", 4),
]

def fmt(n):
    # Форматирование чисел с пробелами
    return '{:,.2f}'.format(float(n)).replace(',', ' ').replace('.00', '')

def calc_levels(order_book, mid_price, percent):
    # Границы диапазона
    rng = (mid_price * (1 - percent / 100), mid_price * (1 + percent / 100))
    # asks: выше mid_price, bids: ниже mid_price
    asks = [(float(p), float(q)) for p, q in order_book['asks'] if rng[0] < float(p) <= rng[1]]
    bids = [(float(p), float(q)) for p, q in order_book['bids'] if rng[0] <= float(p) < rng[1]]

    # Лимитные уровни и объёмы
    ask_count = len(asks)
    bid_count = len(bids)
    ask_volume = sum(q for p, q in asks)
    bid_volume = sum(q for p, q in bids)
    ask_money = sum(p * q for p, q in asks)
    bid_money = sum(p * q for p, q in bids)

    # Сопротивление: max ask, Поддержка: min bid
    resistance = max(asks, default=(mid_price, 0))
    support = min(bids, default=(mid_price, 0))

    # Диапазон
    rng_min = min([p for p, q in bids + asks], default=mid_price)
    rng_max = max([p for p, q in bids + asks], default=mid_price)

    # Кто доминирует?
    side = 'Покупатели' if bid_volume > ask_volume else 'Продавцы'
    dom_pct = abs(bid_volume - ask_volume) / max(bid_volume + ask_volume, 1e-8) * 100

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

def get_trade_idea(stats):
    # Торговая идея по доминирующей стороне (±0.2%)
    s = stats["±0.2%"]
    side = s["side"]
    support_price = s["support"][0]
    resistance_price = s["resistance"][0]
    entry_range = ""
    stop_loss = ""
    take_profit = ""
    if side == "Покупатели":
        entry_range = f"Лонг от поддержки {fmt(support_price-25)}–{fmt(support_price)} $"
        stop_loss = f"Ниже поддержки → {fmt(support_price-50)} $"
        take_profit = f"{fmt(support_price)}–{fmt(support_price+550)} $ (захват ликвидности)"
    else:
        entry_range = f"Шорт от сопротивления {fmt(resistance_price)}–{fmt(resistance_price+25)} $"
        stop_loss = f"Выше сопротивления → {fmt(resistance_price+50)} $"
        take_profit = f"{fmt(resistance_price-550)}–{fmt(resistance_price)} $ (захват ликвидности)"

    return (
        "📌 💡 <b>Торговая идея:</b>\n"
        "<pre>Параметр       | Значение\n"
        "--------------|------------------------------------\n"
        f"✅ Сценарий    | {entry_range}\n"
        f"⛔️ Стоп-лосс   | {stop_loss}\n"
        f"🎯 Цель        | {take_profit}\n"
        f"🔎 Доп. фильтр | Подтверждение объёмом / свечой 1–5м\n"
        "</pre>"
    )

async def get_order_book():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol=SYMBOL, limit=1000)
    await client.close_connection()
    # bids/asks: [(price, qty)]
    depth['bids'] = [(price, qty) for price, qty in depth['bids']]
    depth['asks'] = [(price, qty) for price, qty in depth['asks']]
    return depth

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получить order book
    order_book = await get_order_book()
    all_prices = [float(p) for p, q in order_book['bids'] + order_book['asks']]
    mid_price = sum(all_prices) / len(all_prices) if all_prices else 0

    stats = {}
    for label, pct in DEPTH_LEVELS:
        stats[label] = calc_levels(order_book, mid_price, pct)

    # Формируем текст
    lines = ["<b>📊 BTC/USDT Order Book</b>"]
    for label, pct in DEPTH_LEVELS:
        s = stats[label]
        lines.append(f"\n🔵 {label}")
        lines.append(
            f"📉 Сопротивление: {fmt(s['resistance'][0])} $ ({fmt(s['resistance'][1])} BTC)"
        )
        lines.append(
            f"📊 Поддержка: {fmt(s['support'][0])} $ ({fmt(s['support'][1])} BTC)"
        )
        lines.append(
            f"📈 Диапазон: {fmt(s['rng_min'])} — {fmt(s['rng_max'])}"
        )
        lines.append(
            f"🟥 ask уровней: {s['ask_count']} | 🟩 bid уровней: {s['bid_count']}"
        )
        lines.append(
            f"💰 Объём: 🔻 {fmt(s['ask_volume'])} BTC / ${fmt(s['ask_money'])} | 🔺 {fmt(s['bid_volume'])} BTC / ${fmt(s['bid_money'])}"
        )
        dom_emoji = "🟢" if s['side'] == "Покупатели" else "🔴"
        lines.append(
            f"{dom_emoji*2} {s['side']} доминируют на {int(s['dom_pct'])}%"
        )

    # Добавить торговую идею по доминирующей стороне (±0.2%)
    lines.append("\n" + get_trade_idea(stats))

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
