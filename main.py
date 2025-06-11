
import os
from decimal import Decimal
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
symbol = "BTCUSDT"

depth_levels = {
    "±0.2%": 0.002,
    "±2%": 0.02,
    "±4%": 0.04,
    "±10%": 0.10
}

async def fetch_order_book(session):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=1000"
    async with session.get(url) as response:
        return await response.json()

def calculate_stats(data, price, depth_pct):
    bids = [(Decimal(p), Decimal(q)) for p, q in data['bids']]
    asks = [(Decimal(p), Decimal(q)) for p, q in data['asks']]

    lower = price * (Decimal("1") - depth_pct)
    upper = price * (Decimal("1") + depth_pct)

    filtered_bids = [(p, q) for p, q in bids if lower <= p <= upper]
    filtered_asks = [(p, q) for p, q in asks if lower <= p <= upper]

    buy_volume = sum(p * q for p, q in filtered_bids)
    sell_volume = sum(p * q for p, q in filtered_asks)

    buy_btc = sum(q for _, q in filtered_bids)
    sell_btc = sum(q for _, q in filtered_asks)

    top_support = max([p for p, _ in filtered_bids], default=Decimal("0"))
    top_resistance = min([p for p, _ in filtered_asks], default=Decimal("0"))

    support_btc = sum(q for p, q in filtered_bids if p == top_support)
    resistance_btc = sum(q for p, q in filtered_asks if p == top_resistance)

    dominance = (buy_volume - sell_volume) / (buy_volume + sell_volume + Decimal("0.0001")) * 100
    side = "🟢 Покупатели доминируют" if dominance > 0 else "🔴 Продавцы доминируют"
    emoji = "🟢" if dominance > 0 else "🔴"

    return {
        "range": f"{int(depth_pct*100)}%",
        "support": f"{top_support:.2f} $ ({support_btc:.0f} BTC)",
        "resistance": f"{top_resistance:.2f} $ ({resistance_btc:.0f} BTC)",
        "side": side + f" на {abs(dominance):.0f}%",
        "emoji": emoji
    }

def generate_summary(stats_by_range):
    bullish = sum(1 for stats in stats_by_range.values() if "Покупатели" in stats["side"])
    bearish = sum(1 for stats in stats_by_range.values() if "Продавцы" in stats["side"])

    if bullish > bearish:
        return "Объём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост."
    elif bearish > bullish:
        return "Продавцы преобладают на ключевых уровнях, возможен откат или падение."
    else:
        return "Баланс между покупателями и продавцами — рынок нейтрален."

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        data = await fetch_order_book(session)
        price_data = await session.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
        price = Decimal((await price_data.json())['price'])

        stats_by_range = {}
        for label, pct in depth_levels.items():
            stats_by_range[label] = calculate_stats(data, price, Decimal(str(pct)))

        msg = f"📊 BTC/USDT Order Book\n"
        for label in depth_levels.keys():
            stats = stats_by_range[label]
            msg += f"\n🔵 {label}\n"
            msg += f"📉 Сопротивление: {stats['resistance']}\n"
            msg += f"📊 Поддержка: {stats['support']}\n"
            msg += f"{stats['emoji']} {stats['side']}\n"

        msg += f"\n🧭 Сводка:\n{generate_summary(stats_by_range)}"

        await update.message.reply_text(msg)

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
