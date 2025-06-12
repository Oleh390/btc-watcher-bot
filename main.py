import asyncio
from binance import AsyncClient
from binance.enums import *
from decimal import Decimal
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Только нужные диапазоны!
depth_levels = {
    "±0.2%": 0.002,
    "±0.4%": 0.004,
    "±2%": 0.02,
    "±4%": 0.04,
}

def calculate_stats(depth, price, pct):
    lower = price * (Decimal("1") - Decimal(str(pct)))
    upper = price * (Decimal("1") + Decimal(str(pct)))
    asks = [x for x in depth["asks"] if Decimal(x[0]) <= upper and Decimal(x[0]) >= lower]
    bids = [x for x in depth["bids"] if Decimal(x[0]) >= lower and Decimal(x[0]) <= upper]
    ask_volume = sum(Decimal(qty) * Decimal(price) for price, qty in asks)
    bid_volume = sum(Decimal(qty) * Decimal(price) for price, qty in bids)
    ask_qty = sum(Decimal(qty) for price, qty in asks)
    bid_qty = sum(Decimal(qty) for price, qty in bids)
    ask_levels = len(asks)
    bid_levels = len(bids)
    side = "Покупатели" if bid_volume > ask_volume else "Продавцы"
    dominance = abs(bid_volume - ask_volume) / max(bid_volume, ask_volume) * 100 if max(bid_volume, ask_volume) > 0 else Decimal("0")
    return {
        "lower": lower,
        "upper": upper,
        "ask_volume": ask_volume,
        "bid_volume": bid_volume,
        "ask_qty": ask_qty,
        "bid_qty": bid_qty,
        "ask_levels": ask_levels,
        "bid_levels": bid_levels,
        "side": side,
        "dominance": dominance
    }

async def get_orderbook_stats():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol="BTCUSDT", limit=1000)
    ticker = await client.get_symbol_ticker(symbol="BTCUSDT")
    await client.close_connection()
    price = Decimal(ticker["price"])
    stats_by_range = {}
    for label, pct in depth_levels.items():
        stats_by_range[label] = calculate_stats(depth, price, pct)
    return stats_by_range, price

def format_number(n):
    return f"{n:,.2f}".replace(",", " ")

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats, price = await get_orderbook_stats()
    lines = ["📊 <b>BTC/USDT Order Book</b>\n"]
    for label in ["±0.2%", "±0.4%", "±2%", "±4%"]:
        s = stats[label]
        resistance = format_number(s["upper"])
        support = format_number(s["lower"])
        ask_volume = format_number(s["ask_qty"])
        bid_volume = format_number(s["bid_qty"])
        ask_usd = format_number(s["ask_volume"])
        bid_usd = format_number(s["bid_volume"])
        ask_levels = s["ask_levels"]
        bid_levels = s["bid_levels"]
        dominance = format_number(s["dominance"])
        lines.append(
            f"🔵 <b>{label}</b>\n"
            f"📉 Сопротивление: {resistance} $ ({ask_volume} BTC)\n"
            f"📊 Поддержка: {support} $ ({bid_volume} BTC)\n"
            f"📈 Диапазон: {support} — {resistance}\n"
            f"🟥 ask уровней: {ask_levels} | 🟩 bid уровней: {bid_levels}\n"
            f"💰 Объём: 🔻 {ask_volume} BTC / ${ask_usd} | 🔺 {bid_volume} BTC / ${bid_usd}\n"
            f"{'🟢' if s['side'] == 'Покупатели' else '🔴'} {s['side']} доминируют на {dominance}%\n"
        )

    summary = stats["±0.2%"]["side"]
    lines.append(f"\n🧭 <b>Сводка:</b>\n{summary} преобладают на большинстве уровней, возможен {'рост' if summary == 'Покупатели' else 'откат или падение'}.")

    # Торговая идея для покупателей
    if summary == "Покупатели":
        support = stats["±0.2%"]["lower"]
        s_val = Decimal(support)
        entry_min = format_number(s_val * Decimal("0.995"))
        entry_max = format_number(s_val)
        sl = format_number(s_val * Decimal("0.995") - Decimal("50"))
        tp = format_number(s_val * Decimal("1.005") + Decimal("50"))
        lines.append(
            "\n📌 💡 <b>Торговая идея:</b>\n"
            "<pre>Параметр         | Значение\n"
            "------------------|-------------------------------\n"
            f"✅ Сценарий       | <b>Лонг от поддержки {entry_min}–{entry_max} $</b>\n"
            f"⛔️ Стоп-лосс      | Ниже поддержки → {sl} $\n"
            f"🎯 Цель           | {tp} $ (захват ликвидности)\n"
            f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n</pre>"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
