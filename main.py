
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

    # Плотнейшие уровни по BTC
    support_level = max(filtered_bids, key=lambda x: x[1], default=(Decimal("0"), Decimal("0")))
    resistance_level = max(filtered_asks, key=lambda x: x[1], default=(Decimal("0"), Decimal("0")))

    support_price, support_btc = support_level
    resistance_price, resistance_btc = resistance_level

    dominance = (buy_volume - sell_volume) / (buy_volume + sell_volume + Decimal("0.0001")) * 100
    side = "🟢 Покупатели доминируют" if dominance > 0 else "🔴 Продавцы доминируют"
    emoji = "🟢" if dominance > 0 else "🔴"

    return {
        "range": f"{int(depth_pct * 100)}%",
        "support": f"{support_price:.2f} $ ({support_btc:.0f} BTC)",
        "resistance": f"{resistance_price:.2f} $ ({resistance_btc:.0f} BTC)",
        "side": f"{side} на {abs(dominance):.0f}%",
        "emoji": emoji,
        "buy_btc": f"{buy_btc:.2f}",
        "sell_btc": f"{sell_btc:.2f}",
        "buy_usd": f"{buy_volume:.0f}",
        "sell_usd": f"{sell_volume:.0f}",
        "bid_levels": len(filtered_bids),
        "ask_levels": len(filtered_asks),
        "lower": f"{lower:.2f}",
        "upper": f"{upper:.2f}"
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
            msg += (
                f"\n🔵 ±{label}"
                f"\n📉 Сопротивление: {stats['resistance']}"
                f"\n📊 Поддержка: {stats['support']}"
                f"\n📈 Диапазон: {stats['lower']} — {stats['upper']}"
                f"\n🟥 ask уровней: {stats['ask_levels']} | 🟩 bid уровней: {stats['bid_levels']}"
                f"\n💰 Объём: 🔻 {stats['sell_btc']} BTC / ${stats['sell_usd']} | 🔺 {stats['buy_btc']} BTC / ${stats['buy_usd']}"
                f"\n{stats['emoji']} {stats['side']}\n"
            )

        
    msg += f"\n🧭 Сводка:\n{generate_summary(stats_by_range)}"

    # Генерация торговой идеи при доминировании покупателей
    main_range = stats_by_range["±0.2%"]
    if "Покупатели" in main_range["side"]:
        support_price = main_range["support"].split(" $")[0]
        support_value = Decimal(support_price)
        sl = support_value * Decimal("0.995")
        tp = support_value * Decimal("1.005")
        msg += f"\n\n📌 💡 <b>Торговая идея:</b>\n"
        msg += f"<pre>Параметр         | Значение\n"
        msg += f"------------------|-------------------------------\n"
        msg += f"✅ Сценарий       | Лонг от поддержки {support_value - 25:.0f}–{support_value:.0f} $\n"
        msg += f"⛔ Стоп-лосс      | Ниже поддержки → {sl:.0f} $\n"
        msg += f"🎯 Цель           | {tp:.0f}–{tp + 500:.0f} $ (захват ликвидности)\n"
        msg += f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n</pre>"
    

        await update.message.reply_text(msg)

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
