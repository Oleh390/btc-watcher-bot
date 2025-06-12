import asyncio
from decimal import Decimal
import os
from binance.async_client import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SYMBOL = "BTCUSDT"
DEPTH_LIMIT = 1000

LEVELS = [0.2, 0.4, 2, 4]  # В процентах
FRACTIONS = [lvl / 100 for lvl in LEVELS]

def format_number(n):
    return f"{n:,.2f}".replace(",", " ")

def calc_levels(bids, asks, price, fraction):
    price = Decimal(price)
    delta = price * Decimal(fraction)
    lower = price - delta
    upper = price + delta

    bids_filtered = [b for b in bids if Decimal(b[0]) >= lower]
    asks_filtered = [a for a in asks if Decimal(a[0]) <= upper]

    bid_vol = sum(Decimal(b[1]) for b in bids_filtered)
    ask_vol = sum(Decimal(a[1]) for a in asks_filtered)

    support = min(bids_filtered, key=lambda b: Decimal(b[0])) if bids_filtered else bids[0]
    resistance = max(asks_filtered, key=lambda a: Decimal(a[0])) if asks_filtered else asks[0]

    return {
        "support_price": float(support[0]),
        "support_vol": float(support[1]),
        "resist_price": float(resistance[0]),
        "resist_vol": float(resistance[1]),
        "bid_vol": float(bid_vol),
        "ask_vol": float(ask_vol),
        "bid_levels": len(bids_filtered),
        "ask_levels": len(asks_filtered),
        "range": (float(lower), float(upper))
    }

async def get_order_book():
    client = await AsyncClient.create()
    try:
        depth = await client.get_order_book(symbol=SYMBOL, limit=DEPTH_LIMIT)
        return depth
    finally:
        await client.close_connection()

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    depth = await get_order_book()
    bids = depth['bids']
    asks = depth['asks']
    mid_price = (Decimal(bids[0][0]) + Decimal(asks[0][0])) / 2

    results = []
    for fraction in FRACTIONS:
        stats = calc_levels(bids, asks, mid_price, fraction)
        dom_side = "🟢 Покупатели" if stats['bid_vol'] > stats['ask_vol'] else "🔴 Продавцы"
        dom_percent = abs(stats['bid_vol'] - stats['ask_vol']) / max(stats['bid_vol'], stats['ask_vol']) * 100
        msg = f"""🔵 ±{fraction*100:.1f}%
📉 Сопротивление: {format_number(stats['resist_price'])} $ ({int(stats['resist_vol'])} BTC)
📊 Поддержка: {format_number(stats['support_price'])} $ ({int(stats['support_vol'])} BTC)
📈 Диапазон: {format_number(stats['range'][0])} — {format_number(stats['range'][1])}
🟥 ask уровней: {stats['ask_levels']} | 🟩 bid уровней: {stats['bid_levels']}
💰 Объём: 🔻 {format_number(stats['ask_vol'])} BTC | 🔺 {format_number(stats['bid_vol'])} BTC
{dom_side} доминируют на {int(dom_percent)}%
"""
        results.append((msg, stats, dom_side, dom_percent, fraction))

    # Авто-выбор диапазона для торговой идеи
    # Критерий: максимальный объём на поддержку/сопротивление и >10% доминирование
    best = max(results, key=lambda r: r[3])
    _, best_stats, best_side, _, best_fraction = best

    # Торговая идея (лонг или шорт)
    if "Покупатели" in best_side:
        scenario = f"Лонг от поддержки {format_number(best_stats['support_price']-25)}–{format_number(best_stats['support_price'])} $"
        sl = f"Ниже поддержки → {format_number(best_stats['support_price']-50)} $"
        tp = f"{format_number(best_stats['support_price'])}–{format_number(best_stats['support_price']+500)} $ (захват ликвидности)"
    else:
        scenario = f"Шорт от сопротивления {format_number(best_stats['resist_price'])}–{format_number(best_stats['resist_price']+25)} $"
        sl = f"Выше сопротивления → {format_number(best_stats['resist_price']+50)} $"
        tp = f"{format_number(best_stats['resist_price']-500)}–{format_number(best_stats['resist_price'])} $ (захват ликвидности)"

    summary = "\n".join(r[0] for r in results)
    trade_idea = f"""📌 <b>Торговая идея (авто-выбор диапазона)</b>:
Бот выбрал диапазон ±{best_fraction*100:.1f}%, т.к. здесь максимальный объём и явное доминирование стороны.

<pre>Параметр      | Значение
----------------|---------------------------------------
✅ Сценарий     | {scenario}
⛔️ Стоп-лосс    | {sl}
🎯 Цель         | {tp}
🔎 Доп. фильтр  | Подтверждение объёмом / свечой 1–5м
</pre>"""

    await update.message.reply_text("📊 BTC/USDT Order Book\n\n" + summary + "\n" + trade_idea, parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
