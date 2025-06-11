
import os
import asyncio
import aiohttp
from decimal import Decimal
from dotenv import load_dotenv
import telegram

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_USER_ID")
bot = telegram.Bot(token=TELEGRAM_TOKEN)

symbol = "BTCUSDT"
percent_levels = [0.002, 0.02, 0.04, 0.10]  # ±0.2%, ±2%, ±4%, ±10%

async def fetch_order_book():
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=5000"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

def analyze_order_book(data, current_price):
    results = []
    for level in percent_levels:
        upper_bound = current_price * (1 + level)
        lower_bound = current_price * (1 - level)
        bids = [(Decimal(p), Decimal(q)) for p, q in data["bids"] if lower_bound <= Decimal(p) <= upper_bound]
        asks = [(Decimal(p), Decimal(q)) for p, q in data["asks"] if lower_bound <= Decimal(p) <= upper_bound]

        buy_volume = sum(p * q for p, q in bids)
        sell_volume = sum(p * q for p, q in asks)
        buy_qty = sum(q for _, q in bids)
        sell_qty = sum(q for _, q in asks)

        buy_side = "🟢 Покупатели доминируют"
        sell_side = "🔴 Продавцы доминируют"
        dominance = buy_volume / (buy_volume + sell_volume) * 100 if (buy_volume + sell_volume) > 0 else 0

        results.append({
            "level": level,
            "support": max(bids, default=(Decimal(0), Decimal(0))),
            "resistance": min(asks, default=(Decimal(0), Decimal(0))),
            "dominance": dominance,
            "side": buy_side if dominance >= 50 else sell_side
        })
    return results

def format_message(results):
    msg = "📊 BTC/USDT Order Book

"
    positive_trend = 0

    for r in results:
        pct = int(r["level"] * 100)
        msg += f"🔵 ±{pct}%
"
        msg += f"📉 Сопротивление: {r['resistance'][0]:,.2f} $ ({r['resistance'][1]:.0f} BTC)
"
        msg += f"📊 Поддержка: {r['support'][0]:,.2f} $ ({r['support'][1]:.0f} BTC)
"
        msg += f"{r['side']} на {int(r['dominance'])}%

"
        if r["dominance"] >= 50:
            positive_trend += 1

    summary = "🧭 Сводка:
"
    if positive_trend >= 3:
        summary += "Объём лимитных заявок на покупку преобладает на большинстве уровней — возможен рост цены."
    elif positive_trend <= 1:
        summary += "Продавцы преобладают — возможен откат вниз."
    else:
        summary += "Баланс между покупателями и продавцами — возможен флэт."

    return msg + summary

async def main():
    while True:
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    price_data = await resp.json()
            current_price = Decimal(price_data["price"])

            data = await fetch_order_book()
            results = analyze_order_book(data, current_price)
            message = format_message(results)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        except Exception as e:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"Ошибка: {e}")

        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
