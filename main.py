import asyncio
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

depth_levels = ["±0.2%", "±0.4%", "±2%", "±4%"]
depth_map = {
    "±0.2%": 0.002,
    "±0.4%": 0.004,
    "±2%": 0.02,
    "±4%": 0.04,
}

async def get_orderbook_stats():
    client = await AsyncClient.create()
    ticker = await client.get_symbol_ticker(symbol="BTCUSDT")
    price = Decimal(ticker["price"])
    depth = await client.get_order_book(symbol="BTCUSDT", limit=1000)
    await client.close_connection()

    stats = {}
    for label, pct in depth_map.items():
        lower = price * (1 - Decimal(str(pct)))
        upper = price * (1 + Decimal(str(pct)))
        bids = [(Decimal(p), Decimal(q)) for p, q in depth["bids"] if lower <= Decimal(p) <= upper]
        asks = [(Decimal(p), Decimal(q)) for p, q in depth["asks"] if lower <= Decimal(p) <= upper]
        bid_vol = sum(p * q for p, q in bids)
        ask_vol = sum(p * q for p, q in asks)
        bid_qty = sum(q for _, q in bids)
        ask_qty = sum(q for _, q in asks)
        bid_price = max((p for p, _ in bids), default=Decimal("0"))
        ask_price = min((p for p, _ in asks), default=Decimal("0"))

        stats[label] = {
            "side": "Покупатели" if bid_vol > ask_vol else "Продавцы",
            "bid_vol": bid_vol,
            "ask_vol": ask_vol,
            "bid_qty": bid_qty,
            "ask_qty": ask_qty,
            "bid_price": bid_price,
            "ask_price": ask_price,
            "bid_levels": len(bids),
            "ask_levels": len(asks),
            "price_range": (lower, upper),
            "emoji": "🟢" if bid_vol > ask_vol else "🔴",
            "dominance": round(abs(bid_vol - ask_vol) / max(bid_vol + ask_vol, 1) * 100)
        }

    return stats, price

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats, price = await get_orderbook_stats()
    lines = ["📊 BTC/USDT Order Book\n"]
    for label in depth_levels:
        st = stats[label]
        lines.append(f"🔵 {label}")
        lines.append(f"📉 Сопротивление: {st['ask_price']:.2f} $ ({st['ask_qty']:.0f} BTC)")
        lines.append(f"📊 Поддержка: {st['bid_price']:.2f} $ ({st['bid_qty']:.0f} BTC)")
        r1, r2 = stats[label]["price_range"]
        lines.append(f"📈 Диапазон: {r1:.2f} — {r2:.2f}")
        lines.append(f"🟥 ask уровней: {st['ask_levels']} | 🟩 bid уровней: {st['bid_levels']}")
        lines.append(f"💰 Объём: 🔻 {st['ask_qty']:.2f} BTC / ${st['ask_vol']:.0f} | 🔺 {st['bid_qty']:.2f} BTC / ${st['bid_vol']:.0f}")
        lines.append(f"{st['emoji']} {st['emoji']} {st['side']} доминируют на {st['dominance']}%\n")

    summary = stats["±0.2%"]["side"]
    lines.append("🧭 Сводка:")
    if summary == "Покупатели":
        lines.append("Объём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост.\n")
    else:
        lines.append("Объём лимитных заявок на продажу преобладает на большинстве уровней, возможна коррекция.\n")

    # торговая идея
    support = stats["±0.2%"]["bid_price"]
    s1 = support * Decimal("0.995")
    tp = support * Decimal("1.005")
    lines.append("📌 💡 <b>Торговая идея:</b>")
    lines.append("<pre>Параметр         | Значение")
    lines.append("------------------|-------------------------------")
    lines.append(f"✅ Сценарий       | Лонг от поддержки {support - 25:.0f}–{support:.0f} $")
    lines.append(f"⛔️ Стоп-лосс      | Ниже поддержки → {s1:.0f} $")
    lines.append(f"🎯 Цель           | {support:.0f}–{tp:.0f} $ (захват ликвидности)")
    lines.append(f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м</pre>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()