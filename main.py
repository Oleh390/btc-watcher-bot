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

# Границы глубины стакана
DEPTH_LEVELS = {
    "±±0.2%": 0.002,
    "±±2%": 0.02,
    "±±4%": 0.04,
    "±±10%": 0.10,
    "±±20%": 0.20,
}

def format_number(val, digits=2):
    return f"{val:,.{digits}f}".replace(",", " ")

def calculate_stats(depth, price: Decimal, percent: float):
    lower_bound = price * (Decimal("1") - Decimal(percent))
    upper_bound = price * (Decimal("1") + Decimal(percent))

    ask_volume = bid_volume = 0
    ask_value = bid_value = 0
    ask_levels = bid_levels = 0

    for p, q in depth["asks"]:
        price_level = Decimal(p)
        qty = Decimal(q)
        if lower_bound <= price_level <= upper_bound:
            ask_volume += float(qty)
            ask_value += float(price_level * qty)
            ask_levels += 1

    for p, q in depth["bids"]:
        price_level = Decimal(p)
        qty = Decimal(q)
        if lower_bound <= price_level <= upper_bound:
            bid_volume += float(qty)
            bid_value += float(price_level * qty)
            bid_levels += 1

    return {
        "ask_volume": ask_volume,
        "ask_value": ask_value,
        "ask_levels": ask_levels,
        "bid_volume": bid_volume,
        "bid_value": bid_value,
        "bid_levels": bid_levels,
        "lower": float(lower_bound),
        "upper": float(upper_bound),
    }

async def get_orderbook_stats():
    client = await AsyncClient.create()
    try:
        ticker = await client.get_symbol_ticker(symbol="BTCUSDT")
        current_price = Decimal(ticker["price"])
        depth = await client.get_order_book(symbol="BTCUSDT", limit=1000)
        result = {}
        for label, pct in DEPTH_LEVELS.items():
            result[label] = calculate_stats(depth, current_price, pct)
        return result, current_price
    finally:
        await client.close_connection()

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats, current_price = await get_orderbook_stats()
    lines = ["📊 BTC/USDT Order Book\n"]
    summary = []

    for label, s in stats.items():
        total_ask = s["ask_value"]
        total_bid = s["bid_value"]
        dom = total_bid - total_ask
        dom_pct = int((dom / (total_bid + total_ask)) * 100) if (total_bid + total_ask) > 0 else 0
        dom_label = "🟢 Покупатели" if dom_pct > 0 else "🔴 Продавцы"

        lines.append(
            f"\n🔵 {label}\n"
            f"📉 Сопротивление: {format_number(s['upper'])} $ ({int(s['ask_volume'])} BTC)\n"
            f"📊 Поддержка: {format_number(s['lower'])} $ ({int(s['bid_volume'])} BTC)\n"
            f"📈 Диапазон: {format_number(s['lower'])} — {format_number(s['upper'])}\n"
            f"🟥 ask уровней: {s['ask_levels']} | 🟩 bid уровней: {s['bid_levels']}\n"
            f"💰 Объём: 🔻 {s['ask_volume']:.2f} BTC / ${format_number(s['ask_value'], 0)} | "
            f"🔺 {s['bid_volume']:.2f} BTC / ${format_number(s['bid_value'], 0)}\n"
            f"{dom_label} доминируют на {abs(dom_pct)}%"
        )

        summary.append(dom_pct)

    # Сводка:
    bull_doms = [x for x in summary if x > 0]
    bear_doms = [x for x in summary if x < 0]
    if len(bull_doms) > len(bear_doms):
        lines.append("\n\n🧭 Сводка:\nОбъём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост.")
    elif len(bear_doms) > len(bull_doms):
        lines.append("\n\n🧭 Сводка:\nОбъём лимитных заявок на продажу преобладает на большинстве уровней, возможен откат.")
    else:
        lines.append("\n\n🧭 Сводка:\nСилы покупателей и продавцов сбалансированы.")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
