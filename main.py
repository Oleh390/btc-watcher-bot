import os
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_USER_ID"))

SYMBOL = "BTCUSDT"
PRECISIONS = [0.002, 0.004, 0.02, 0.04, 0.1]  # ±0.2%, ±0.4%, ±2%, ±4%, ±10%
PRECISIONS_LABELS = ["±0.2%", "±0.4%", "±2%", "±4%", "±10%"]

async def get_order_book():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol=SYMBOL, limit=1000)
    await client.close_connection()
    bids = [(Decimal(price), Decimal(amount)) for price, amount in depth["bids"]]
    asks = [(Decimal(price), Decimal(amount)) for price, amount in depth["asks"]]
    return bids, asks

def filter_by_range(orders, price, pct, side):
    low = price * (Decimal(1) - Decimal(pct))
    high = price * (Decimal(1) + Decimal(pct))
    if side == "bid":
        filtered = [o for o in orders if low <= o[0] <= price]
    else:
        filtered = [o for o in orders if price <= o[0] <= high]
    return filtered

def calc_stats(bids, asks, price, pct):
    filtered_bids = filter_by_range(bids, price, pct, "bid")
    filtered_asks = filter_by_range(asks, price, pct, "ask")
    # Сортировка для поиска поддержки и сопротивления
    filtered_bids.sort(reverse=True)   # bid — от большего к меньшему
    filtered_asks.sort()               # ask — от меньшего к большему
    support_price, support_amt = filtered_bids[0] if filtered_bids else (Decimal(0), Decimal(0))
    resistance_price, resistance_amt = filtered_asks[0] if filtered_asks else (Decimal(0), Decimal(0))
    total_bid = sum(amt for _, amt in filtered_bids)
    total_ask = sum(amt for _, amt in filtered_asks)
    total_bid_usd = sum(price * amt for price, amt in filtered_bids)
    total_ask_usd = sum(price * amt for price, amt in filtered_asks)
    bid_lvls = len(filtered_bids)
    ask_lvls = len(filtered_asks)
    dominance = int(round(100 * total_bid / (total_bid + total_ask), 0)) if (total_bid + total_ask) else 0
    dom_side = "Покупатели" if dominance >= 50 else "Продавцы"
    diff = dominance if dominance >= 50 else 100 - dominance
    dom_emoji = "🟢" if dominance >= 50 else "🔴"
    price_low = min(filtered_bids[0][0] if filtered_bids else price, filtered_asks[0][0] if filtered_asks else price)
    price_high = max(filtered_bids[0][0] if filtered_bids else price, filtered_asks[0][0] if filtered_asks else price)
    return {
        "label": None,
        "support": support_price,
        "support_amt": support_amt,
        "resist": resistance_price,
        "resist_amt": resistance_amt,
        "bid_lvls": bid_lvls,
        "ask_lvls": ask_lvls,
        "total_bid": total_bid,
        "total_ask": total_ask,
        "total_bid_usd": total_bid_usd,
        "total_ask_usd": total_ask_usd,
        "dominance": dominance,
        "dom_side": dom_side,
        "diff": diff,
        "dom_emoji": dom_emoji,
        "price_low": price_low,
        "price_high": price_high
    }

def format_number(x):
    if isinstance(x, Decimal):
        x = float(x)
    if x >= 10000:
        return f"{x:,.0f}".replace(",", " ")
    if x >= 1000:
        return f"{x:,.2f}".replace(",", " ")
    return str(round(x, 2))

def format_stats(stats, label):
    return (
        f"\n🔵 {label}\n"
        f"📉 Сопротивление: {format_number(stats['resist'])} $ ({format_number(stats['resist_amt'])} BTC)\n"
        f"📊 Поддержка: {format_number(stats['support'])} $ ({format_number(stats['support_amt'])} BTC)\n"
        f"📈 Диапазон: {format_number(stats['price_low'])} — {format_number(stats['price_high'])}\n"
        f"🟥 ask уровней: {stats['ask_lvls']} | 🟩 bid уровней: {stats['bid_lvls']}\n"
        f"💰 Объём: 🔻 {format_number(stats['total_bid'])} BTC / ${format_number(stats['total_bid_usd'])} | "
        f"🔺 {format_number(stats['total_ask'])} BTC / ${format_number(stats['total_ask_usd'])}\n"
        f"{stats['dom_emoji']} {stats['dom_side']} доминируют на {stats['diff']}%\n"
    )

def generate_idea(support_price):
    support_from = format_number(support_price)
    support_to = format_number(support_price + Decimal('25'))
    sl = format_number(support_price - Decimal('50'))
    tp_from = format_number(support_price + Decimal('50'))
    tp_to = format_number(support_price + Decimal('100'))
    idea = (
        "\n📌 💡 <b>Торговая идея:</b>\n"
        "<pre>Параметр         | Значение\n"
        "------------------|-------------------------------\n"
        f"✅ Сценарий       | Лонг от поддержки {support_from}–{support_to} $\n"
        f"⛔️ Стоп-лосс      | Ниже поддержки → {sl} $\n"
        f"🎯 Цель           | {tp_from}–{tp_to} $ (захват ликвидности)\n"
        f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
        "</pre>"
    )
    return idea

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bids, asks = await get_order_book()
    price = (bids[0][0] + asks[0][0]) / 2
    message = "📊 BTC/USDT Order Book\n"
    all_stats = []
    for pct, label in zip(PRECISIONS, PRECISIONS_LABELS):
        stats = calc_stats(bids, asks, price, pct)
        stats['label'] = label
        all_stats.append(stats)
        message += format_stats(stats, label)
    # Добавляем "Торговая идея" по самой узкой поддержке
    message += generate_idea(all_stats[0]['support'])
    await update.message.reply_text(message, parse_mode="HTML")

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
