import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from binance.client import Client
from decimal import Decimal

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
USER_ID = int(os.environ.get("TELEGRAM_USER_ID"))

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

PCT = 0.005  # 0.5%

def get_orderbook_stats(symbol="BTCUSDT", pct=0.005):
    depth = client.get_order_book(symbol=symbol, limit=1000)
    bids = [(Decimal(price), Decimal(qty)) for price, qty in depth["bids"]]
    asks = [(Decimal(price), Decimal(qty)) for price, qty in depth["asks"]]
    price = (bids[0][0] + asks[0][0]) / 2  # mid price

    upper = price * (1 + Decimal(pct))
    lower = price * (1 - Decimal(pct))

    ask_within = [(p, q) for p, q in asks if p <= upper]
    bid_within = [(p, q) for p, q in bids if p >= lower]

    res = {
        "resistance": float(max(ask_within, default=(0, 0))[0]) if ask_within else None,
        "resistance_qty": float(sum(q for p, q in ask_within)),
        "support": float(min(bid_within, default=(0, 0))[0]) if bid_within else None,
        "support_qty": float(sum(q for p, q in bid_within)),
        "range_low": float(min(bid_within, default=(price,))[0]),
        "range_high": float(max(ask_within, default=(price,))[0]),
        "ask_lvls": len(ask_within),
        "bid_lvls": len(bid_within),
        "ask_vol": float(sum(q for p, q in ask_within)),
        "bid_vol": float(sum(q for p, q in bid_within)),
        "ask_usd": float(sum(p*q for p, q in ask_within)),
        "bid_usd": float(sum(p*q for p, q in bid_within)),
        "side": "Покупатели" if sum(q for p, q in bid_within) > sum(q for p, q in ask_within) else "Продавцы",
        "side_pct": abs(sum(q for p, q in bid_within) - sum(q for p, q in ask_within)) / max(sum(q for p, q in bid_within), 1) * 100,
        "mid_price": float(price)
    }
    return res

def make_message(stats, symbol="BTCUSDT"):
    asset = symbol.replace("USDT", "")
    msg = (
        f"📊 {asset}/USDT Order Book (±0.5%)\n\n"
        f"💵 Цена: {stats['mid_price']:.2f} $\n"
        f"📉 Сопротивление: {stats['resistance']:.2f} $ ({stats['resistance_qty']:.2f} {asset})\n"
        f"📊 Поддержка: {stats['support']:.2f} $ ({stats['support_qty']:.2f} {asset})\n"
        f"📈 Диапазон: {stats['range_low']:.2f} — {stats['range_high']:.2f}\n"
        f"🟥 ask уровней: {stats['ask_lvls']} | 🟩 bid уровней: {stats['bid_lvls']}\n"
        f"💰 Объём: 🔻 {stats['ask_vol']:.2f} {asset} / ${stats['ask_usd']:.0f} | 🔺 {stats['bid_vol']:.2f} {asset} / ${stats['bid_usd']:.0f}\n"
        f"🟢 {'Покупатели' if stats['side']=='Покупатели' else 'Продавцы'} доминируют на {int(stats['side_pct'])}%\n\n"
        "📌 Торговая идея:\n"
        "<pre>Параметр         | Значение\n"
        "------------------|-------------------------------\n"
        "✅ Сценарий       | Лонг от поддержки {support}-{sup_top} $\n"
        "⛔️ Стоп-лосс      | Ниже поддержки → {stop_loss} $\n"
        "🎯 Цель           | {target_min}-{target_max} $ (захват ликвидности)\n"
        "🔎 Доп. фильтр    | Подтверждение объёмом / свечой 1–5м\n"
        "</pre>\n"
    ).format(
        support=int(stats['support']),
        sup_top=int(stats['support']+25),
        stop_loss=int(stats['support']-50),
        target_min=int(stats['resistance']),
        target_max=int(stats['resistance']+50),
    )
    return msg

async def btc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        await update.message.reply_text("Нет доступа.")
        return
    stats = get_orderbook_stats("BTCUSDT", PCT)
    msg = make_message(stats, "BTCUSDT")
    await update.message.reply_text(msg, parse_mode="HTML")

async def eth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        await update.message.reply_text("Нет доступа.")
        return
    stats = get_orderbook_stats("ETHUSDT", PCT)
    msg = make_message(stats, "ETHUSDT")
    await update.message.reply_text(msg, parse_mode="HTML")

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("btc", btc))
    app.add_handler(CommandHandler("eth", eth))
    app.run_polling()
