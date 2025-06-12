import asyncio
import os
from decimal import Decimal
from dotenv import load_dotenv
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

DEPTH_LEVELS = [0.002, 0.004, 0.02, 0.04]

def calculate_depth_range(price: Decimal, depth: float):
    lower = price * (Decimal("1") - Decimal(str(depth)))
    upper = price * (Decimal("1") + Decimal(str(depth)))
    return lower, upper

def calculate_stats(depth, bids, asks, price):
    lower, upper = calculate_depth_range(price, depth)

    bid_volume = ask_volume = Decimal("0")
    bid_value = ask_value = Decimal("0")
    bid_levels = ask_levels = 0
    support_price = resistance_price = None

    for bid_price, bid_qty in bids:
        if lower <= bid_price <= upper:
            bid_volume += bid_qty
            bid_value += bid_price * bid_qty
            bid_levels += 1
            if support_price is None or bid_price < support_price:
                support_price = bid_price

    for ask_price, ask_qty in asks:
        if lower <= ask_price <= upper:
            ask_volume += ask_qty
            ask_value += ask_price * ask_qty
            ask_levels += 1
            if resistance_price is None or ask_price > resistance_price:
                resistance_price = ask_price

    if support_price is None:
        support_price = bids[0][0]
    if resistance_price is None:
        resistance_price = asks[0][0]

    total = bid_volume + ask_volume
    dominance = (bid_volume / total * 100).quantize(Decimal("1")) if total > 0 else Decimal("0")

    return {
        "depth": depth,
        "support_price": support_price,
        "resistance_price": resistance_price,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "bid_value": bid_value,
        "ask_value": ask_value,
        "bid_levels": bid_levels,
        "ask_levels": ask_levels,
        "dominance": dominance,
        "lower": lower,
        "upper": upper
    }

async def get_orderbook_stats():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol="BTCUSDT", limit=1000)
    await client.close_connection()

    bids = [(Decimal(bid[0]), Decimal(bid[1])) for bid in depth["bids"]]
    asks = [(Decimal(ask[0]), Decimal(ask[1])) for ask in depth["asks"]]

    price = (bids[0][0] + asks[0][0]) / 2
    stats_by_depth = {}
    for d in DEPTH_LEVELS:
        stats_by_depth[d] = calculate_stats(d, bids, asks, price)

    return stats_by_depth, price

def format_stats(stats_by_depth, price):
    lines = ["📊 <b>BTC/USDT Order Book</b>\n"]
    for depth in DEPTH_LEVELS:
        stats = stats_by_depth[depth]
        lines.append(f"\n🔵 ±{int(depth * 100)}%")
        lines.append(f"📉 Сопротивление: {stats['resistance_price']:.2f} $ ({int(stats['ask_volume'])} BTC)")
        lines.append(f"📊 Поддержка: {stats['support_price']:.2f} $ ({int(stats['bid_volume'])} BTC)")
        lines.append(f"📈 Диапазон: {stats['lower']:.2f} — {stats['upper']:.2f}")
        lines.append(f"🟥 ask уровней: {stats['ask_levels']} | 🟩 bid уровней: {stats['bid_levels']}")
        lines.append(f"💰 Объём: 🔻 {stats['ask_volume']:.2f} BTC / ${stats['ask_value']:.0f} | 🔺 {stats['bid_volume']:.2f} BTC / ${stats['bid_value']:.0f}")
        lines.append(f"🟢 Покупатели доминируют на {stats['dominance']}%")

    strongest = max(stats_by_depth.values(), key=lambda s: s["dominance"])
    sl = strongest["support_price"] * Decimal("0.995")
    tp = strongest["support_price"] * Decimal("1.005")

    lines.append("\n🧭 <b>Сводка:</b>")
    lines.append(f"Объём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост.\n")
    lines.append("📌 💡 <b>Торговая идея:</b>")
    lines.append("<pre>Параметр         | Значение")
    lines.append("------------------|-------------------------------")
    lines.append(f"✅ Сценарий       | Лонг от поддержки {strongest['support_price'] - 25:.0f}–{strongest['support_price']:.0f} $")
    lines.append(f"⛔️ Стоп-лосс      | Ниже поддержки → {sl:.0f} $")
    lines.append(f"🎯 Цель           | {strongest['support_price']:.0f}–{tp:.0f} $ (захват ликвидности)")
    lines.append("🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м</pre>")
    return "\n".join(lines)

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats, price = await get_orderbook_stats()
    text = format_stats(stats, price)
    await update.message.reply_text(text, parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()