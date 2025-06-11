
import asyncio
import aiohttp
import os
import telegram
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_USER_ID")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

symbol = "BTCUSDT"
depth_levels = {
    "±0.2%": 0.002,
    "±2%": 0.02,
    "±4%": 0.04,
    "±10%": 0.10
}

async def fetch_order_book(session):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=1000"
    async with session.get(url) as response:
        return await response.json()

def calculate_stats(data, price, depth_pct):
    lower = price * (Decimal('1') - Decimal(str(depth_pct)))
    upper = price * (Decimal('1') + Decimal(str(depth_pct)))
    bids = [order for order in data['bids'] if lower <= Decimal(order[0]) <= upper]
    asks = [order for order in data['asks'] if lower <= Decimal(order[0]) <= upper]
    bid_volume = sum(Decimal(qty) for price, qty in bids)
    ask_volume = sum(Decimal(qty) for price, qty in asks)
    bid_value = sum(Decimal(price) * Decimal(qty) for price, qty in bids)
    ask_value = sum(Decimal(price) * Decimal(qty) for price, qty in asks)
    total_volume = bid_volume + ask_volume
    side = "Покупатели" if bid_value > ask_value else "Продавцы"
    dominance = abs(bid_value - ask_value) / (bid_value + ask_value) * 100 if (bid_value + ask_value) != 0 else Decimal('0')
    return {
        "bids": bid_volume,
        "asks": ask_volume,
        "bid_value": bid_value,
        "ask_value": ask_value,
        "side": side,
        "dominance": dominance,
        "support": f"{bids[0][0]} $ ({bids[0][1]} BTC)" if bids else "-",
        "resistance": f"{asks[0][0]} $ ({asks[0][1]} BTC)" if asks else "-",
        "range": f"{lower:.2f} — {upper:.2f}",
        "bid_levels": len(bids),
        "ask_levels": len(asks)
    }
def generate_summary(stats_by_range):
    bullish = sum(1 for stats in stats_by_range.values() if "Покупатели" in stats["side"])
    bearish = sum(1 for stats in stats_by_range.values() if "Продавцы" in stats["side"])

    if bullish > bearish:
        return "Объём лимитных заявок на покупку преобладает на большинстве уровней, возможен рост."
    elif bearish > bullish:
        return "Продавцы преобладают на ключевых уровнях, возможен откат или падение."
    else:
        return "Баланс между покупателями и продавцами — рынок нейтрален."

async def main():
    async with aiohttp.ClientSession() as session:
        data = await fetch_order_book(session)
        mark_price_data = await session.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
        price = Decimal((await mark_price_data.json())['price'])

        stats_by_range = {}
        for label, pct in depth_levels.items():
            stats_by_range[label] = calculate_stats(data, price, pct)

        msg = f"📊 BTC/USDT Order Book\n"
        for label in depth_levels.keys():
            stats = stats_by_range[label]
            msg += f"\n🔵 {label}\n"
            msg += f"📉 Сопротивление: {stats['resistance']}\n"
            msg += f"📊 Поддержка: {stats['support']}\n"
            msg += f"{stats['emoji']} {stats['side']}\n"

        msg += f"\n🧭 Сводка:\n{generate_summary(stats_by_range)}"

        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

if __name__ == "__main__":
    asyncio.run(main())
