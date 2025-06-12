import asyncio
import logging
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

depth_ranges = {
    "±0.2%": 0.002,
    "±2%": 0.02,
    "±4%": 0.04,
    "±10%": 0.10,
    "±20%": 0.20,
}

def calculate_stats(depth, price, pct):
    lower = price * (Decimal("1") - Decimal(pct))
    upper = price * (Decimal("1") + Decimal(pct))
    ask_volume = bid_volume = 0
    ask_value = bid_value = 0
    ask_levels = bid_levels = 0
    for order in depth["asks"]:
        p, q = Decimal(order[0]), Decimal(order[1])
        if lower <= p <= upper:
            ask_volume += float(q)
            ask_value += float(p * q)
            ask_levels += 1
    for order in depth["bids"]:
        p, q = Decimal(order[0]), Decimal(order[1])
        if lower <= p <= upper:
            bid_volume += float(q)
            bid_value += float(p * q)
            bid_levels += 1
    return {
        "ask_volume": ask_volume,
        "ask_value": ask_value,
        "ask_levels": ask_levels,
        "bid_volume": bid_volume,
        "bid_value": bid_value,
        "bid_levels": bid_levels,
        "lower": lower,
        "upper": upper,
    }

def format_number(val, digits=2):
    return f"{val:,.{digits}f}".replace(",", " ")

async def get_orderbook_stats():
    client = await AsyncClient.create()
    try:
        ticker = await client.get_symbol_ticker(symbol="BTCUSDT")
        current_price = Decimal(ticker["price"])
        depth = await client.get_order_book(symbol="BTCUSDT", limit=1000)
        result = {}
        for label, pct in depth_ranges.items():
            stats = calculate_stats(depth, current_price, pct)
            result[label] = stats
        return result, current_price
    finally:
        await client.close_connection()

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stats, price = await get_orderbook_stats()
        lines = ["📊 <b>BTC/USDT Order Book</b>\\n"]
        for label, s in stats.items():
            dom = s["bid_value"] - s["ask_value"]
            total = s["bid_value"] + s["ask_value"]
            dom_pct = int((dom / total) * 100) if total > 0 else 0
            emoji = "🟢 Покупатели" if dom_pct >= 0 else "🔴 Продавцы"
            lines.append(
                f"🔵 {label}\\n"
                f"📉 Сопротивление: {format_number(s['upper'])} $ ({s['ask_volume']:.0f} BTC)\\n"
                f"📊 Поддержка: {format_number(s['lower'])} $ ({s['bid_volume']:.0f} BTC)\\n"
                f"📈 Диапазон: {format_number(s['lower'])} — {format_number(s['upper'])}\\n"
                f"🟥 ask уровней: {s['ask_levels']} | 🟩 bid уровней: {s['bid_levels']}\\n"
                f"💰 Объём: 🔻 {s['ask_volume']:.2f} BTC / ${format_number(s['ask_value'], 0)} | "
                f"🔺 {s['bid_volume']:.2f} BTC / ${format_number(s['bid_value'], 0)}\\n"
                f"{emoji} доминируют на {abs(dom_pct)}%\\n"
            )
        await update.message.reply_text("\\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logging.exception("Ошибка в /watch")
        await update.message.reply_text("Произошла ошибка. Попробуй позже.")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
