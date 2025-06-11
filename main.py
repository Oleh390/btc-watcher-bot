import os
import json
import asyncio
import websockets
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
SYMBOL = "btcusdt"
DEPTH_STREAM = f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth@100ms"

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Ошибка отправки сообщения в Telegram:", e)

def calculate_stats(bids, asks, percent_level):
    def filter_by_price(levels, price_ref, is_bid):
        range_min = price_ref * (1 - percent_level)
        range_max = price_ref * (1 + percent_level)

        filtered = []
        for p, q in levels:
            price = float(p)
            qty = float(q)

            if is_bid and range_min <= price <= price_ref:
                filtered.append([price, qty])
            elif not is_bid and price_ref <= price <= range_max:
                filtered.append([price, qty])

        return filtered

    if not bids or not asks:
        return None

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid_price = (best_bid + best_ask) / 2

    filtered_bids = filter_by_price(bids, mid_price, is_bid=True)
    filtered_asks = filter_by_price(asks, mid_price, is_bid=False)

    buy_volume = sum(p * q for p, q in filtered_bids)
    sell_volume = sum(p * q for p, q in filtered_asks)
    buy_btc = sum(q for _, q in filtered_bids)
    sell_btc = sum(q for _, q in filtered_asks)

    dominance = (
        (buy_volume - sell_volume) / (buy_volume + sell_volume) * 100
        if (buy_volume + sell_volume) > 0 else 0
    )
    return {
        "level": percent_level,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "buy_btc": buy_btc,
        "sell_btc": sell_btc,
        "dominance": dominance,
        "support": best_bid,
        "resistance": best_ask
    }

def format_message(stats_list):
    message = f"📊 *BTC/USDT Order Book*"
    for stats in stats_list:
        emoji = "🟢" if stats["dominance"] > 0 else "🔴"
        side = "Покупатели" if stats["dominance"] > 0 else "Продавцы"
        level = f"±{int(stats['level']*100)}%"

        message += (
            f"\n\n{emoji} *{side} доминируют на {abs(stats['dominance']):.1f}%* ({level})"
            f"\n🔼 Buy Volume: {stats['buy_btc']:.0f} BTC (~{stats['buy_volume'] / 1_000_000:.2f}M $)"
            f"\n🔽 Sell Volume: {stats['sell_btc']:.0f} BTC (~{stats['sell_volume'] / 1_000_000:.2f}M $)"
            f"\n📈 Разница: {(stats['buy_btc'] - stats['sell_btc']):+.0f} BTC ({(stats['buy_volume'] - stats['sell_volume']) / 1_000_000:+.2f}M $)"
        )

    message += (
        f"\n\n📌 Плотность ордеров (±0.1%):"
        f"\n📉 Сопротивление: {stats_list[0]['resistance']:.0f} $"
        f"\n📊 Поддержка: {stats_list[0]['support']:.0f} $"
    )

    dominant = stats_list[0]["dominance"]
    if dominant > 20:
        recommendation = "🚀 Возможен импульс вверх"
    elif dominant < -20:
        recommendation = "⚠️ Возможен импульс вниз"
    else:
        recommendation = "📊 Баланс спроса и предложения"

    message += f"\n\n🧭 *Рекомендация для скальпинга:* {recommendation}"
    return message

async def handle_depth():
    async with websockets.connect(DEPTH_STREAM) as ws:
        while True:
            try:
                data = await ws.recv()
                json_data = json.loads(data)
                bids = json_data.get("bids", [])
                asks = json_data.get("asks", [])

                if not bids or not asks:
                    continue

                stats_list = []
                for level in [0.001, 0.002, 0.02, 0.1]:  # ±0.1%, 0.2%, 2%, 10%
                    stats = calculate_stats(bids, asks, level)
                    if stats:
                        stats_list.append(stats)

                if stats_list:
                    message = format_message(stats_list)
                    send_telegram_message(message)

                await asyncio.sleep(5)

            except Exception as e:
                print("Ошибка в WebSocket соединении:", e)
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(handle_depth())