import os
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
USER_ID = int(os.getenv('TELEGRAM_USER_ID', '437873124'))  # твой ID по умолчанию

PAIR = 'BTCUSDT'
PCT = 0.005  # ±0.5% глубина

async def get_orderbook_stats(pair: str, pct: float):
    client = await AsyncClient.create()
    depth = await client.get_order_book(symbol=pair)
    await client.close_connection()

    bids = [(Decimal(p), Decimal(q)) for p, q in depth['bids']]
    asks = [(Decimal(p), Decimal(q)) for p, q in depth['asks']]
    mid_price = (bids[0][0] + asks[0][0]) / 2

    lower = mid_price * Decimal(1 - pct)
    upper = mid_price * Decimal(1 + pct)

    bid_vol, ask_vol = Decimal(0), Decimal(0)
    bid_levels, ask_levels = 0, 0
    support, resistance = None, None
    support_vol, resistance_vol = Decimal(0), Decimal(0)

    for price, qty in bids:
        if price >= lower:
            bid_vol += qty
            bid_levels += 1
            if not support:
                support = price
                support_vol = qty
        else:
            break

    for price, qty in asks:
        if price <= upper:
            ask_vol += qty
            ask_levels += 1
            if not resistance:
                resistance = price
                resistance_vol = qty
        else:
            break

    dom_side = "Покупатели" if bid_vol > ask_vol else "Продавцы"
    dom_pct = int(abs(bid_vol - ask_vol) / max(bid_vol, ask_vol) * 100) if max(bid_vol, ask_vol) > 0 else 0

    return {
        'mid_price': mid_price,
        'lower': lower,
        'upper': upper,
        'bid_volume': bid_vol,
        'ask_volume': ask_vol,
        'bid_levels': bid_levels,
        'ask_levels': ask_levels,
        'support': support,
        'support_vol': support_vol,
        'resistance': resistance,
        'resistance_vol': resistance_vol,
        'dom_side': dom_side,
        'dom_pct': dom_pct
    }

def format_number(n, prec=2):
    return f"{n:,.{prec}f}".replace(",", " ")

async def send_orderbook(update: Update, context: ContextTypes.DEFAULT_TYPE, pair: str):
    stats = await get_orderbook_stats(pair, PCT)
    emoji_side = "🟢" if stats['dom_side'] == "Покупатели" else "🔴"

    msg = f"""📊 {pair}/USDT Order Book

💵 Цена: {format_number(stats['mid_price'], 2)} $
🔵 ±0.5%
📉 Сопротивление: {format_number(stats['resistance'], 2)} $ ({format_number(stats['resistance_vol'], 2)} BTC)
📊 Поддержка: {format_number(stats['support'], 2)} $ ({format_number(stats['support_vol'], 2)} BTC)
📈 Диапазон: {format_number(stats['lower'], 2)} — {format_number(stats['upper'], 2)}
🟥 ask уровней: {stats['ask_levels']} | 🟩 bid уровней: {stats['bid_levels']}
💰 Объём: 🔻 {format_number(stats['ask_volume'], 2)} BTC | 🔺 {format_number(stats['bid_volume'], 2)} BTC
{emoji_side} {stats['dom_side']} доминируют на {stats['dom_pct']}%

📌 💡 <b>Торговая идея:</b>
<pre>Параметр       | Значение
----------------|-------------------------------
✅ Сценарий     | Лонг от поддержки {format_number(stats['support'], 2)} $
⛔ Стоп-лосс    | Ниже поддержки → {format_number(stats['support'] * Decimal("0.995"), 2)} $
🎯 Цель         | {format_number(stats['support'] * Decimal('1.005'), 2)}–{format_number(stats['support'] * Decimal('1.01'), 2)} $ (захват ликвидности)
🔎 Доп. фильтр  | Подтверждение объёмом / свечой 1–5м
</pre>
"""
    await context.bot.send_message(chat_id=USER_ID, text=msg, parse_mode='HTML')

async def btc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_orderbook(update, context, 'BTCUSDT')

async def eth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_orderbook(update, context, 'ETHUSDT')

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("btc", btc))
    app.add_handler(CommandHandler("eth", eth))
    app.run_polling()
