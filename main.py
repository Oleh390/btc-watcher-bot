import asyncio
import os
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID"))

SYMBOL = "BTCUSDT"
DEPTH_LEVELS = {
    "±0.2%": 0.002,
    "±2%": 0.02,
    "±4%": 0.04,
    "±10%": 0.10
}

def calculate_stats(data, price, depth_pct):
    lower = price * (1 - float(depth_pct))
    upper = price * (1 + float(depth_pct))

    bids = [Decimal(b[1]) for b in data['bids'] if lower <= float(b[0]) <= upper]
    asks = [Decimal(a[1]) for a in data['asks'] if lower <= float(a[0]) <= upper]

    bid_volume = sum(bids)
    ask_volume = sum(asks)

    side = "Покупатели" if bid_volume > ask_volume else "Продавцы"
    dominance = abs(bid_volume - ask_volume) / max(bid_volume + ask_volume, Decimal(1)) * 100

    support = min(float(b[0]) for b in data['bids'] if lower <= float(b[0]) <= upper)
    resistance = max(float(a[0]) for a in data['asks'] if lower <= float(a[0]) <= upper)

    return {
        "support": f"{support:.2f} $ ({int(sum(bids))} BTC)",
        "resistance": f"{resistance:.2f} $ ({int(sum(asks))} BTC)",
        "buy_vol": bid_volume,
        "sell_vol": ask_volume,
        "side": side,
        "emoji": "🟢" if side == "Покупатели" else "🔴",
        "dominance": dominance,
        "range": f"{lower:.2f} — {upper:.2f}",
        "bid_levels": len(data['bids']),
        "ask_levels": len(data['asks'])
    }

async def get_orderbook_stats():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol=SYMBOL, limit=1000)
    ticker = await client.get_symbol_ticker(symbol=SYMBOL)
    price = Decimal(ticker["price"])
    await client.close_connection()

    stats = {}
    for label, pct in DEPTH_LEVELS.items():
        stats[label] = calculate_stats(depth, price, pct)

    return stats, price

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats, price = await get_orderbook_stats()

    lines = ["📊 <b>BTC/USDT Order Book</b>"]
    for label, data in stats.items():
        lines.append(f"🔵 {label}")
        lines.append(f"📉 Сопротивление: {data['resistance']}")
        lines.append(f"📊 Поддержка: {data['support']}")
        lines.append(f"{data['emoji']} {data['side']} доминируют на {int(data['dominance'])}%")
        lines.append(f"📦 Объём: 🟢 {data['buy_vol']:.2f} BTC / 🔴 {data['sell_vol']:.2f}")
        lines.append(f"📊 Диапазон: {data['range']}")
        lines.append(f"📈 Уровней: 🟢 {data['bid_levels']} | 🔴 {data['ask_levels']}")
        lines.append("")

    main_range = stats["±0.2%"]
    if main_range["side"] == "Покупатели":
        support_price = main_range["support"].split(" $")[0]
        support_value = Decimal(support_price)
        sl = support_value * Decimal("0.995")
        tp = support_value * Decimal("1.005")

        lines.append("📌 Сводка: Объём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост.")

        lines.append("📌💡 <b>Торговая идея:</b>")
        lines.append("<pre>Параметр      | Значение")
        lines.append("--------------|-----------------------------------------")
        lines.append(f"<b>✅ Сценарий</b>     | <b>Лонг от поддержки {support_value - 25:.0f}–{support_value:.0f} $</b>")
        lines.append(f"⛔ Стоп-лосс     | Ниже поддержки → {sl:.0f} $")
        lines.append(f"<b>🎯 Цель</b>         | <b>{support_value + 75:.0f}–{tp:.0f} $</b> (захват ликвидности)")
        lines.append(f"🔎 Доп. фильтр   | Подтверждение объёмом / свечой 1–5м</pre>")

    await update.message.reply_text("".join(lines), parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
