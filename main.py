import os
import asyncio
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

depth_percents = [0.002, 0.02, 0.04, 0.10, 0.20]

def calculate_stats(depth_pct, price, asks, bids):
    lower = float(price) * (1 - depth_pct)
    upper = float(price) * (1 + depth_pct)

    asks_filtered = [order for order in asks if lower <= float(order[0]) <= upper]
    bids_filtered = [order for order in bids if lower <= float(order[0]) <= upper]

    ask_volume = sum(float(order[1]) for order in asks_filtered)
    bid_volume = sum(float(order[1]) for order in bids_filtered)

    ask_levels = len(asks_filtered)
    bid_levels = len(bids_filtered)

    total_volume = ask_volume + bid_volume
    if total_volume == 0:
        dominance = 0
    else:
        dominance = ((bid_volume - ask_volume) / total_volume) * 100

    return {
        "ask_volume": round(ask_volume, 2),
        "bid_volume": round(bid_volume, 2),
        "ask_usd": round(ask_volume * float(price), 2),
        "bid_usd": round(bid_volume * float(price), 2),
        "ask_levels": ask_levels,
        "bid_levels": bid_levels,
        "dominance": round(abs(dominance)),
        "side": "Покупатели" if dominance > 0 else "Продавцы",
        "emoji": "🟢" if dominance > 0 else "🔴",
        "support": min([float(order[0]) for order in bids_filtered], default=0),
        "resistance": max([float(order[0]) for order in asks_filtered], default=0),
        "range": (lower, upper),
    }

async def get_orderbook_stats():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol="BTCUSDT", limit=1000)
    ticker = await client.get_symbol_ticker(symbol="BTCUSDT")
    await client.close_connection()

    price = Decimal(ticker["price"])
    asks = depth["asks"]
    bids = depth["bids"]

    stats = {}
    for pct in depth_percents:
        stats[f"±{int(pct * 100)}%"] = calculate_stats(pct, price, asks, bids)

    return stats, price

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats, price = await get_orderbook_stats()
    lines = [f"📊 <b>BTC/USDT Order Book</b>\n"]

    for label, stat in stats.items():
        lines.append(f"🔵 <b>{label}</b>")
        lines.append(f"📉 Сопротивление: {stat['resistance']:.2f} $ ({stat['ask_volume']} BTC)")
        lines.append(f"📊 Поддержка: {stat['support']:.2f} $ ({stat['bid_volume']} BTC)")
        lines.append(f"📏 Диапазон: {stat['range'][0]:.2f} — {stat['range'][1]:.2f}")
        lines.append(f"📉 ask уровней: {stat['ask_levels']} │ 🟩 bid уровней: {stat['bid_levels']}")
        lines.append(f"📉 Объём: 🔻 {stat['ask_volume']} BTC / ${stat['ask_usd']} │ 🔺 {stat['bid_volume']} BTC / ${stat['bid_usd']}")
        lines.append(f"{stat['emoji']} {stat['side']} доминируют на {stat['dominance']}%\n")

    summary = stats["±0.2%"]["side"]
    lines.append(f"📌 <b>Сводка:</b> Объём лимитных заявок на {'покупку' if summary == 'Покупатели' else 'продажу'} преобладает на большинстве уровней, возможен {'рост' if summary == 'Покупатели' else 'откат или падение'}.")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()