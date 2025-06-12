from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")


async def get_orderbook_stats():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol='BTCUSDT', limit=1000)
    await client.close_connection()

    asks = [(Decimal(price), Decimal(qty)) for price, qty in depth['asks']]
    bids = [(Decimal(price), Decimal(qty)) for price, qty in depth['bids']]

    mid_price = (asks[0][0] + bids[0][0]) / 2

    ranges = {
        '±0.2%': Decimal('0.002'),
        '±0.4%': Decimal('0.004'),
        '±2%': Decimal('0.02'),
        '±4%': Decimal('0.04'),
    }

    lines = ["📈 BTC/USDT Order Book\n"]

    for label, pct in ranges.items():
        lower = mid_price * (1 - pct)
        upper = mid_price * (1 + pct)

        filtered_asks = [(p, q) for p, q in asks if lower <= p <= upper]
        filtered_bids = [(p, q) for p, q in bids if lower <= p <= upper]

        ask_vol = sum(q for _, q in filtered_asks)
        bid_vol = sum(q for _, q in filtered_bids)

        resistance = max(filtered_asks, key=lambda x: x[0], default=(Decimal(0), Decimal(0)))
        support = min(filtered_bids, key=lambda x: x[0], default=(Decimal(0), Decimal(0)))

        ask_levels = len(filtered_asks)
        bid_levels = len(filtered_bids)

        total_buy = bid_vol
        total_sell = ask_vol
        dominance = round((total_buy - total_sell) / (total_buy + total_sell + Decimal('1e-8')) * 100)

        emoji = "🔼" if dominance > 0 else "🔽"
        trend = "📉 Продавцы доминируют" if dominance < 0 else "📈 Покупатели доминируют"

        lines.append(f"🔹 {label}\n" +
                     f"🔻 Сопротивление: {resistance[0]:,.2f} $ ({resistance[1]:.0f} BTC)" + "\n" +
                     f"📊 Поддержка: {support[0]:,.2f} $ ({support[1]:.0f} BTC)" + "\n" +
                     f"🔼 Диапазон: {lower:,.2f} — {upper:,.2f}" + "\n" +
                     f"🔺 ask уровней: {ask_levels} | 🔽 bid уровней: {bid_levels}" + "\n" +
                     f"💰 Объём: 🔻 {total_sell:.2f} BTC / ${total_sell * mid_price:,.0f} | 🔺 {total_buy:.2f} BTC / ${total_buy * mid_price:,.0f}" + "\n" +
                     f"🟢 {trend} на {abs(dominance)}%\n")

    # Авто торговая идея если доминируют покупатели
    if dominance > 10:
        support_price = support[0]
        sl = support_price * Decimal("0.997")
        tp = support_price * Decimal("1.005")
        tp2 = support_price * Decimal("1.01")
        lines.append("\n📌 🌝 <b>Торговая идея:</b>")
        lines.append("<pre>Параметр         | Значение\n" +
                     "------------------|-------------------------------\n" +
                     f"✅ Сценарий       | Лонг от поддержки {support_price * Decimal('0.997'):.0f}–{support_price:.0f} $\n" +
                     f"⛔️ Стоп-лосс      | Ниже поддержки → {sl:.0f} $\n" +
                     f"🌟 Цель           | {tp:.0f}–{tp2:.0f} $ (захват ликвидности)\n" +
                     f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м</pre>")

    return "\n".join(lines)


async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await get_orderbook_stats()
    await update.message.reply_text(msg, parse_mode="HTML")


if __name__ == '__main__':
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
