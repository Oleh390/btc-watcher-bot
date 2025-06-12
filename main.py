TELEGRAM_TOKEN = "7830848319:AAHjRmoCT_1u8ufoIqWDYqi8aT1oFya_Lvs"
TELEGRAM_USER_ID = "437873124"

import asyncio
import logging
from decimal import Decimal
from binance import AsyncClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Убираем лишние логи от binance
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEPTH_LEVELS = [0.002, 0.004, 0.02, 0.04]  # ±0.2%, ±0.4%, ±2%, ±4%
PAIR = "BTCUSDT"

def round_btc(val):
    return float(Decimal(val).quantize(Decimal('1.00')))

def round_usd(val):
    return float(Decimal(val).quantize(Decimal('1')))

async def get_order_book():
    async with AsyncClient() as client:
        data = await client.get_order_book(symbol=PAIR, limit=1000)
        return data["bids"], data["asks"]

def analyze_depth(bids, asks, price, pct):
    upper = price * (1 + pct)
    lower = price * (1 - pct)
    bids_in = [b for b in bids if lower <= float(b[0]) <= price]
    asks_in = [a for a in asks if price <= float(a[0]) <= upper]

    bid_vol = sum(float(b[1]) for b in bids_in)
    ask_vol = sum(float(a[1]) for a in asks_in)
    bid_lvl = len(bids_in)
    ask_lvl = len(asks_in)

    support = min(float(b[0]) for b in bids_in) if bids_in else 0
    resistance = max(float(a[0]) for a in asks_in) if asks_in else 0

    return {
        "support": support,
        "resistance": resistance,
        "bid_vol": bid_vol,
        "ask_vol": ask_vol,
        "bid_lvl": bid_lvl,
        "ask_lvl": ask_lvl,
        "lower": lower,
        "upper": upper,
    }

def build_message(depth_stats):
    msg = "<b>📊 BTC/USDT Order Book</b>\n\n"
    best_idea = None
    best_volume = 0

    for i, (label, stat) in enumerate(depth_stats.items()):
        buyers_domi = int(100 * stat['bid_vol'] / max(stat['ask_vol'] + stat['bid_vol'], 1))
        sellers_domi = 100 - buyers_domi

        # выбираем диапазон для авто-идеи
        if stat['bid_vol'] > best_volume and buyers_domi > 10:
            best_idea = (label, stat)
            best_volume = stat['bid_vol']

        domi_emoji = "🟢 Покупатели" if buyers_domi > sellers_domi else "🔴 Продавцы"
        domi_val = buyers_domi if buyers_domi > sellers_domi else sellers_domi

        msg += (
            f"🔵 ±{label}\n"
            f"📉 Сопротивление: {round_usd(stat['resistance'])} $ ({round_btc(stat['ask_vol'])} BTC)\n"
            f"📊 Поддержка: {round_usd(stat['support'])} $ ({round_btc(stat['bid_vol'])} BTC)\n"
            f"📈 Диапазон: {round_usd(stat['lower'])} — {round_usd(stat['upper'])}\n"
            f"🟥 ask уровней: {stat['ask_lvl']} | 🟩 bid уровней: {stat['bid_lvl']}\n"
            f"💰 Объём: 🔻 {round_btc(stat['ask_vol'])} BTC | 🔺 {round_btc(stat['bid_vol'])} BTC\n"
            f"{domi_emoji} доминируют на {domi_val}%\n\n"
        )
    # Торговая идея на лучшем диапазоне
    if best_idea:
        label, stat = best_idea
        support = round_usd(stat['support'])
        sl = support - 500
        tp1 = support + 600
        tp2 = support + 1200

        msg += (
            "📌 <b>Торговая идея (авто-выбор диапазона):</b>\n"
            "<pre>Параметр    | Значение\n"
            "----------------|----------------------------------------\n"
            f"✅ Сценарий     | Лонг от поддержки {support-25}-{support} $\n"
            f"⛔️ Стоп-лосс    | Ниже поддержки → {sl} $\n"
            f"🎯 Цель         | {tp1}-{tp2} $ (захват ликвидности)\n"
            f"🔎 Доп. фильтр  | Подтверждение объёмом / свечой 1–5м\n"
            "</pre>"
        )

    return msg

async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загрузка данных по стакану...", parse_mode="HTML")
    bids, asks = await get_order_book()
    price = float(asks[0][0])  # best ask (или можешь заменить на среднее между лучшей ценой bid/ask)
    depth_stats = {}

    for pct in DEPTH_LEVELS:
        label = f"{pct*100:.1f}%"
        stat = analyze_depth(bids, asks, price, pct)
        depth_stats[label] = stat

    msg = build_message(depth_stats)
    await update.message.reply_text(msg, parse_mode="HTML")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("watch", handle_watch))
    app.run_polling()

if __name__ == "__main__":
    main()
