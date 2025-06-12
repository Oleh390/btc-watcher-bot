import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_USER_ID")

bot = Bot(token=TOKEN)

logging.basicConfig(level=logging.INFO)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth"
BINANCE_MARK_PRICE_URL = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
DEPTH_LEVELS = [0.002, 0.02, 0.04, 0.10, 0.20]

async def fetch_price():
    async with aiohttp.ClientSession() as session:
        async with session.get(BINANCE_MARK_PRICE_URL) as resp:
            data = await resp.json()
            return float(data["markPrice"])

def filter_depth(depth, lower_bound, upper_bound):
    return [(price, qty) for price, qty in depth if lower_bound <= price <= upper_bound]

def get_max_level(depth):
    return max(depth, key=lambda x: x[1]) if depth else (0, 0)

async def handle_depth_update(data, current_price):
    asks = [(float(price), float(qty)) for price, qty in data.get("asks", [])]
    bids = [(float(price), float(qty)) for price, qty in data.get("bids", [])]

    message = f"\ud83d\udcca BTC/USDT Order Book\n"

    for level in DEPTH_LEVELS:
        pct_label = f"\u00b1{int(level*100)}%"
        lower = current_price * (1 - level)
        upper = current_price * (1 + level)

        filtered_asks = filter_depth(asks, lower, upper)
        filtered_bids = filter_depth(bids, lower, upper)

        ask_volume = sum(qty for _, qty in filtered_asks)
        bid_volume = sum(qty for _, qty in filtered_bids)

        ask_value = sum(price * qty for price, qty in filtered_asks)
        bid_value = sum(price * qty for price, qty in filtered_bids)

        max_ask_price, max_ask_qty = get_max_level(filtered_asks)
        max_bid_price, max_bid_qty = get_max_level(filtered_bids)

        dominance = "\ud83d\udd34 Продавцы доминируют" if ask_value > bid_value else "\ud83d\udfe2 Покупатели доминируют"
        dominance_pct = abs(bid_value - ask_value) / max(bid_value, ask_value) * 100 if max(bid_value, ask_value) > 0 else 0

        message += f"\n\U0001f539 {pct_label}\n"
        message += f"\ud83d\udd39 Сопротивление: {max_ask_price:.2f} $ ({max_ask_qty:.0f} BTC)\n"
        message += f"\ud83d\udd39 Поддержка: {max_bid_price:.2f} $ ({max_bid_qty:.0f} BTC)\n"
        message += f"\ud83d\udcb0 Объём: \ud83d\udd3b {ask_volume:.2f} BTC / ${ask_value:,.0f} | \ud83d\udd3a {bid_volume:.2f} BTC / ${bid_value:,.0f}\n"
        message += f"{dominance} на {dominance_pct:.0f}%\n"

    await bot.send_message(chat_id=CHAT_ID, text=message)

async def main():
    current_price = await fetch_price()

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(BINANCE_WS_URL) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await handle_depth_update(data, current_price)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

if __name__ == '__main__':
    asyncio.run(main())
