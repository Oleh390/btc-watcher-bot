
import os
import time
import asyncio
import requests
import websockets
import json
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

SYMBOL = "btcusdt"
WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth@100ms"

PERCENTAGE_LEVELS = [0.001, 0.002, 0.004, 0.01]

async def send_telegram_message(message: str):
    await bot.send_message(chat_id=TELEGRAM_USER_ID, text=message)

async def analyze_order_book():
    async with websockets.connect(WS_URL) as ws:
        while True:
            try:
                data = await ws.recv()
                order_book = json.loads(data)

                bids = [[float(price), float(quantity)] for price, quantity in order_book["bids"]]
                asks = [[float(price), float(quantity)] for price, quantity in order_book["asks"]]

                mid_price = (bids[0][0] + asks[0][0]) / 2

                levels = []

                for pct in PERCENTAGE_LEVELS:
                    buy_volume = sell_volume = 0
                    lower_bound = mid_price * (1 - pct)
                    upper_bound = mid_price * (1 + pct)

                    support = resistance = None
                    support_vol = resistance_vol = 0

                    for price, quantity in bids:
                        if lower_bound <= price <= upper_bound:
                            buy_volume += price * quantity
                            if not support or price > support:
                                support = price
                                support_vol = quantity

                    for price, quantity in asks:
                        if lower_bound <= price <= upper_bound:
                            sell_volume += price * quantity
                            if not resistance or price < resistance:
                                resistance = price
                                resistance_vol = quantity

                    total_volume = buy_volume + sell_volume
                    if total_volume == 0:
                        dominance = 0
                    else:
                        dominance = ((buy_volume - sell_volume) / total_volume) * 100

                    dominance_side = "🟢 Покупатели доминируют" if dominance >= 0 else "🔴 Продавцы доминируют"
                    dominance = abs(round(dominance))

                    levels.append({
                        "range": f"{int(pct * 100)}%",
                        "support": support,
                        "support_vol": round(support_vol, 2),
                        "resistance": resistance,
                        "resistance_vol": round(resistance_vol, 2),
                        "dominance": dominance,
                        "side": dominance_side
                    })

                message = f"📊 BTC/USDT Order Book\n"
                for lvl in levels:
                    message += (
                        f"🔵 ±{lvl['range']}\n"
                        f"📉 Сопротивление: {lvl['resistance']:,} $ ({lvl['resistance_vol']} BTC)\n"
                        f"📊 Поддержка: {lvl['support']:,} $ ({lvl['support_vol']} BTC)\n"
                        f"{lvl['side']} на {lvl['dominance']}%\n\n"
                    )

                message += "🧭 Сводка: анализ лимитных ордеров по уровням"

                await send_telegram_message(message)
                await asyncio.sleep(30)

            except Exception as e:
                print(f"Ошибка: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(analyze_order_book())
