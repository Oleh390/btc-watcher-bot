import websocket
import json
import requests
import threading
import time

TELEGRAM_BOT_TOKEN = '7830848319:AAHjRmoCT_1u8ufoIqWDYqi8aT1oFya_Lvs'
TELEGRAM_USER_ID = '437873124'
SYMBOL = 'btcusdt'
AGGREGATION_WINDOW = 0.3  # 300ms
MIN_USD_VOLUME = 250_000
DEPTH_LEVEL = 20

lock = threading.Lock()
buffer = []

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_USER_ID,
        "text": text
    }
    try:
        requests.post(url, json=data)
    except Exception as e:
        print("Ошибка Telegram:", e)

def analyze_depth(snapshot):
    try:
        bids = snapshot['bids']
        asks = snapshot['asks']
        current_price = (float(bids[0][0]) + float(asks[0][0])) / 2

        range_min = current_price * 0.999
        range_max = current_price * 1.001

        buy_volume = sum(float(price) * float(amount) for price, amount in bids if range_min <= float(price) <= current_price)
        sell_volume = sum(float(price) * float(amount) for price, amount in asks if current_price <= float(price) <= range_max)

        total_volume = buy_volume + sell_volume
        if total_volume < MIN_USD_VOLUME:
            return

        dominance = "покупатели" if buy_volume > sell_volume else "продавцы"
        percent = (max(buy_volume, sell_volume) / total_volume) * 100

        delta_btc = abs(buy_volume - sell_volume) / current_price
        delta_usdt = abs(buy_volume - sell_volume)

        resistance = float(asks[0][0])
        support = float(bids[0][0])

        recommendation = (
            "Возможен импульс вверх" if buy_volume > sell_volume else
            "Возможен импульс вниз" if sell_volume > buy_volume else
            "Рынок в балансе. Наблюдение"
        )

        message = (
            f"📊 BTC/USDT Order Book\n\n"
            f"{'🟢' if buy_volume > sell_volume else '🔴'} {dominance.capitalize()} доминируют на {percent:.0f}%\n"
            f"🔼 Buy Volume: {buy_volume / current_price:.0f} BTC (~{buy_volume:,.0f} USDT)\n"
            f"🔽 Sell Volume: {sell_volume / current_price:.0f} BTC (~{sell_volume:,.0f} USDT)\n"
            f"📈 Разница: {delta_btc:.0f} BTC ({delta_usdt:,.0f} USDT)\n\n"
            f"📏 Плотность ордеров (±0.1%):\n"
            f"📉 Сопротивление: {resistance:,.2f} $\n"
            f"📊 Поддержка: {support:,.2f} $\n\n"
            f"🧭 Рекомендация для скальпинга: {recommendation}"
        )

        send_telegram_message(message)
        print(message)

    except Exception as e:
        print("Ошибка при анализе стакана:", e)

def fetch_order_book():
    while True:
        try:
            url = f"https://api.binance.com/api/v3/depth?symbol={SYMBOL.upper()}&limit={DEPTH_LEVEL}"
            response = requests.get(url)
            snapshot = response.json()
            analyze_depth(snapshot)
        except Exception as e:
            print("Ошибка при получении стакана:", e)
        time.sleep(AGGREGATION_WINDOW)

if __name__ == "__main__":
    threading.Thread(target=fetch_order_book).start()
