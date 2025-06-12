import asyncio
from binance import AsyncClient
from decimal import Decimal
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
SYMBOL = "BTCUSDT"
DEPTH_LIMIT = 1000

RANGES = [0.002, 0.004, 0.02, 0.04]  # ±0.2%, ±0.4%, ±2%, ±4%

async def get_order_book():
    async with AsyncClient() as client:
        depth = await client.get_order_book(symbol=SYMBOL, limit=DEPTH_LIMIT)
        return depth

def calc_range(price, pct):
    delta = price * pct
    return float(price - delta), float(price + delta)

def find_max_level(levels, lower, upper, is_bid=True):
    # Ищем лимитку с максимальным объёмом в диапазоне
    max_qty = 0
    max_price = None
    total_qty = 0
    for price, qty in levels:
        if lower <= price <= upper:
            total_qty += qty
            if qty > max_qty:
                max_qty = qty
                max_price = price
    return max_price, max_qty, total_qty

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    depth = await get_order_book()
    asks = [(float(price), float(qty)) for price, qty in depth["asks"]]
    bids = [(float(price), float(qty)) for price, qty in depth["bids"]]

    # Получаем актуальную цену как среднее между лучшим бидом и аском
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = (best_bid + best_ask) / 2

    messages = []
    stats = {}

    for pct in RANGES:
        low, high = calc_range(mid_price, pct)
        # ask: сопротивление = min цена в диапазоне с max объёмом
        ask_price, ask_qty, ask_sum = find_max_level(asks, mid_price, high, is_bid=False)
        # bid: поддержка = max цена в диапазоне с max объёмом
        bid_price, bid_qty, bid_sum = find_max_level(bids, low, mid_price, is_bid=True)

        ask_levels = [price for price, qty in asks if mid_price <= price <= high]
        bid_levels = [price for price, qty in bids if low <= price <= mid_price]

        # Объёмы в $
        ask_usd = ask_sum * mid_price
        bid_usd = bid_sum * mid_price

        dom_side = "Покупатели" if bid_sum > ask_sum else "Продавцы"
        dom_pct = int(100 * abs(bid_sum - ask_sum) / (bid_sum + ask_sum)) if (bid_sum + ask_sum) > 0 else 0
        color = "🟢" if dom_side == "Покупатели" else "🔴"

        # Формируем блок по диапазону
        label = f"±{pct*100:.1f}%"
        msg = (
            f"\n🔵 {label}\n"
            f"📉 Сопротивление: {ask_price:,.2f} $ ({int(ask_qty)} BTC)\n"
            f"📊 Поддержка: {bid_price:,.2f} $ ({int(bid_qty)} BTC)\n"
            f"📈 Диапазон: {low:,.2f} — {high:,.2f}\n"
            f"🟥 ask уровней: {len(ask_levels)} | 🟩 bid уровней: {len(bid_levels)}\n"
            f"💰 Объём: 🔻 {ask_sum:.2f} BTC / ${ask_usd:,.0f} | 🔺 {bid_sum:.2f} BTC / ${bid_usd:,.0f}\n"
            f"{color*2} {dom_side} доминируют на {dom_pct}%"
        )
        messages.append(msg)
        stats[pct] = {
            "dom_pct": dom_pct, "dom_side": dom_side,
            "support": (bid_price, bid_qty), "resist": (ask_price, ask_qty),
            "low": low, "high": high
        }

    # Авто-выбор торговой идеи: ищем диапазон с макс доминированием (но не 0.2%, если разница слишком мала)
    best_pct = max(stats, key=lambda x: stats[x]["dom_pct"])
    idea = stats[best_pct]
    # Только если доминирование уверенное (>5%), иначе не давать идею
    trade_idea = ""
    if idea["dom_pct"] > 5:
        side = "Лонг" if idea["dom_side"] == "Покупатели" else "Шорт"
        support_from = int(idea["support"][0] - idea["support"][1])
        support_to = int(idea["support"][0])
        stop = int(idea["support"][0] - 500 if side == "Лонг" else idea["support"][0] + 500)
        target_from = int(idea["support"][0] + 600 if side == "Лонг" else idea["support"][0] - 600)
        target_to = int(idea["support"][0] + 1100 if side == "Лонг" else idea["support"][0] - 1100)
        trade_idea = (
            "\n\n📌💡 <b>Торговая идея (авто-выбор диапазона):</b>\n"
            "<pre>Параметр         | Значение\n"
            "------------------|-------------------------------\n"
            f"✅ Сценарий       | {side} от поддержки {support_from}-{support_to} $\n"
            f"⛔️ Стоп-лосс      | {'Ниже' if side=='Лонг' else 'Выше'} поддержки → {stop} $\n"
            f"🎯 Цель           | {target_from}-{target_to} $ (захват ликвидности)\n"
            f"🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
            "</pre>"
            f"\n<i>Бот выбрал диапазон {best_pct*100:.1f}%, т.к. здесь максимальный объём на {'поддержку' if side=='Лонг' else 'сопротивление'} и явное доминирование {idea['dom_side'].lower()}.</i>"
        )

    await update.message.reply_text(
        f"📊 BTC/USDT Order Book\n" + "\n".join(messages) + trade_idea,
        parse_mode="HTML"
    )

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()
