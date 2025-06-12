import asyncio
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))

depth_ranges = [
    0.002,  # ±0.2%
    0.004,  # ±0.4%
    0.02,   # ±2%
    0.04,   # ±4%
    0.10    # ±10%
]

depth_labels = [
    "±0.2%",
    "±0.4%",
    "±2%",
    "±4%",
    "±10%",
]

async def get_order_book():
    client = await AsyncClient.create()
    try:
        order_book = await client.get_order_book(symbol="BTCUSDT", limit=1000)
        bids = [(float(price), float(amount)) for price, amount in order_book['bids']]
        asks = [(float(price), float(amount)) for price, amount in order_book['asks']]
        return bids, asks
    finally:
        await client.close_connection()

def calc_stats(bids, asks, range_pct):
    if not bids or not asks:
        return {}
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = (best_bid + best_ask) / 2

    low = mid_price * (1 - range_pct)
    high = mid_price * (1 + range_pct)

    bid_vol = sum(amount for price, amount in bids if price >= low and price <= mid_price)
    ask_vol = sum(amount for price, amount in asks if price <= high and price >= mid_price)

    bid_usd = sum(amount * price for price, amount in bids if price >= low and price <= mid_price)
    ask_usd = sum(amount * price for price, amount in asks if price <= high and price >= mid_price)

    resistance = max((price, amount) for price, amount in asks if price <= high and price >= mid_price)
    support = min((price, amount) for price, amount in bids if price >= low and price <= mid_price)

    return {
        "label": f"±±{int(range_pct*100)}%" if range_pct < 0.01 else f"±{int(range_pct*100)}%",
        "support": support,
        "resistance": resistance,
        "bid_vol": bid_vol,
        "ask_vol": ask_vol,
        "bid_usd": bid_usd,
        "ask_usd": ask_usd,
        "low": low,
        "high": high
    }

def format_stats(stats):
    text = ""
    for s in stats:
        sup_price, sup_amt = s["support"]
        res_price, res_amt = s["resistance"]
        text += f"\n🔵 {s['label']}\n"
        text += f"📉 Сопротивление: {res_price:,.2f} $ ({int(res_amt)} BTC)\n"
        text += f"📊 Поддержка: {sup_price:,.2f} $ ({int(sup_amt)} BTC)\n"
        text += f"📈 Диапазон: {s['low']:,.2f} — {s['high']:,.2f}\n"
        text += f"🟥 ask уровней: 1000 | 🟩 bid уровней: 1000\n"
        text += f"💰 Объём: 🔻 {s['ask_vol']:.2f} BTC / ${int(s['ask_usd']):,} | 🔺 {s['bid_vol']:.2f} BTC / ${int(s['bid_usd']):,}\n"
        dom = "Покупатели доминируют" if s['bid_vol'] > s['ask_vol'] else "Продавцы доминируют"
        percent = int(abs(s['bid_vol'] - s['ask_vol']) / max(s['bid_vol'], s['ask_vol']) * 100) if max(s['bid_vol'], s['ask_vol']) > 0 else 0
        text += f"🟢 {dom} на {percent}%\n"
    return text

def trading_idea(stats):
    support = stats[0]["support"][0]
    resistance = stats[0]["resistance"][0]
    stop_loss = support - 0.5 * (resistance - support)
    target = resistance + (resistance - support)
    return (
        "<b>📌 💡 Торговая идея:</b>\n"
        "<pre>Параметр         | Значение\n"
        "------------------|-------------------------------\n"
        f"✅ Сценарий       | Лонг от поддержки {support:,.0f}–{resistance:,.0f} $\n"
        f"⛔️ Стоп-лосс      | Ниже поддержки → {stop_loss:,.0f} $\n"
        f"🎯 Цель           | {resistance:,.0f}–{target:,.0f} $ (захват ликвидности)\n"
        f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
        "</pre>"
    )

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bids, asks = await get_order_book()
    stats = [calc_stats(bids, asks, rng) for rng in depth_ranges]
    text = "📊 BTC/USDT Order Book\n"
    text += format_stats(stats)
    text += "\n" + trading_idea(stats)
    await update.message.reply_text(text, parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
