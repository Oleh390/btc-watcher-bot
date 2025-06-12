import os
import asyncio
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN

load_dotenv()

PAIR = "BTCUSDT"
PERCENTS = [0.2, 0.4, 2, 4]  # В процентах
LIMIT = 1000

def fmt(num, digits=2):
    if isinstance(num, float):
        num = Decimal(str(num))
    if num >= 1000:
        return f"{num.quantize(Decimal('1'), rounding=ROUND_DOWN):,}".replace(',', ' ')
    fmtstr = f"{{0:.{digits}f}}"
    return fmtstr.format(float(num))

def get_side_dominance(bid_volume, ask_volume):
    if bid_volume > ask_volume:
        return "buy", bid_volume, ask_volume, int((bid_volume - ask_volume) / (bid_volume + ask_volume) * 100)
    else:
        return "sell", bid_volume, ask_volume, int((ask_volume - bid_volume) / (bid_volume + ask_volume) * 100)

async def get_order_book():
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol=PAIR, limit=LIMIT)
    await client.close_connection()
    bids = [(float(price), float(amount)) for price, amount in depth["bids"]]
    asks = [(float(price), float(amount)) for price, amount in depth["asks"]]
    return bids, asks

def calc_levels(bids, asks, percent, last_price):
    p = percent / 100
    min_price = last_price * (1 - p)
    max_price = last_price * (1 + p)

    bids_filtered = [b for b in bids if min_price <= b[0] <= last_price]
    asks_filtered = [a for a in asks if last_price <= a[0] <= max_price]
    bid_levels = len(bids_filtered)
    ask_levels = len(asks_filtered)
    bid_volume = sum(b[1] for b in bids_filtered)
    ask_volume = sum(a[1] for a in asks_filtered)
    best_bid = max(bids_filtered, default=(0, 0))[0] if bids_filtered else 0
    best_ask = min(asks_filtered, default=(0, 0))[0] if asks_filtered else 0
    support = min(bids_filtered, default=(0, 0))[0] if bids_filtered else 0
    resistance = max(asks_filtered, default=(0, 0))[0] if asks_filtered else 0
    return {
        "percent": percent,
        "min_price": min_price,
        "max_price": max_price,
        "bid_levels": bid_levels,
        "ask_levels": ask_levels,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "support": support,
        "resistance": resistance,
    }

def get_emoji(side):
    return "🟢" if side == "buy" else "🔴"

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bids, asks = await get_order_book()
    last_price = asks[0][0] if asks and bids and asks[0][0] > bids[0][0] else (bids[0][0] if bids else 0)
    book_lines = ["📊 BTC/USDT Order Book\n"]

    stats_by_level = {}
    for percent in PERCENTS:
        stats = calc_levels(bids, asks, percent, last_price)
        stats_by_level[percent] = stats

        dominance_side, bid_vol, ask_vol, dom_percent = get_side_dominance(stats["bid_volume"], stats["ask_volume"])
        emoji = get_emoji(dominance_side)
        book_lines.append(
            f"🔵 ±{percent}%\n"
            f"📉 Сопротивление: {fmt(stats['resistance'])} $ ({fmt(stats['ask_volume'], 0)} BTC)\n"
            f"📊 Поддержка: {fmt(stats['support'])} $ ({fmt(stats['bid_volume'], 0)} BTC)\n"
            f"📈 Диапазон: {fmt(stats['min_price'])} — {fmt(stats['max_price'])}\n"
            f"🟥 ask уровней: {stats['ask_levels']} | 🟩 bid уровней: {stats['bid_levels']}\n"
            f"💰 Объём: 🔻 {fmt(stats['ask_volume'])} BTC | 🔺 {fmt(stats['bid_volume'])} BTC\n"
            f"{emoji*2} {'Покупатели' if dominance_side == 'buy' else 'Продавцы'} доминируют на {abs(dom_percent)}%\n"
        )

    # Выбор лучшего диапазона для "Торговой идеи"
    best_percent = max(PERCENTS, key=lambda p: abs(stats_by_level[p]["bid_volume"] - stats_by_level[p]["ask_volume"]))
    best = stats_by_level[best_percent]
    dominance_side, _, _, dom_percent = get_side_dominance(best["bid_volume"], best["ask_volume"])
    scenario = (
        f"Лонг от поддержки {fmt(best['support'])}–{fmt(best['best_bid'])} $"
        if dominance_side == "buy"
        else f"Шорт от сопротивления {fmt(best['best_ask'])}–{fmt(best['resistance'])} $"
    )
    stop_loss = (
        f"Ниже поддержки → {fmt(best['support'] * 0.995)} $"
        if dominance_side == "buy"
        else f"Выше сопротивления → {fmt(best['resistance'] * 1.005)} $"
    )
    take_profit = (
        f"{fmt(best['best_bid'])}–{fmt(best['best_bid'] + (best['best_bid'] * 0.5/100))} $ (захват ликвидности)"
        if dominance_side == "buy"
        else f"{fmt(best['best_ask'])}–{fmt(best['best_ask'] - (best['best_ask'] * 0.5/100))} $ (захват ликвидности)"
    )

    book_lines.append(
        "\n📌 💡 <b>Торговая идея (авто-выбор диапазона):</b>\n"
        f'<pre>Параметр         | Значение\n'
        f'------------------|-------------------------------\n'
        f'✅ Сценарий       | {scenario}\n'
        f'⛔ Стоп-лосс      | {stop_loss}\n'
        f'🎯 Цель           | {take_profit}\n'
        f'🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n'
        f'</pre>\n'
        f'Бот выбрал диапазон ±{best_percent}%, '
        f'т.к. здесь максимальный {"объём на поддержку" if dominance_side == "buy" else "объём на сопротивление"} '
        f'и явное доминирование {"покупателей" if dominance_side == "buy" else "продавцов"} ({abs(dom_percent)}%)'
    )

    await update.message.reply_text(
        "\n".join(book_lines), parse_mode="HTML"
    )

if __name__ == "__main__":
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
