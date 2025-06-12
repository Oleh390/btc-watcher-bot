from decimal import Decimal

def get_orderbook_stats(symbol, pct=0.005):
    # Получаем данные стакана через Binance API
    from binance.client import Client
    import os

    client = Client(api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET"))
    depth = client.get_order_book(symbol=symbol, limit=1000)

    bids = [(Decimal(price), Decimal(amount)) for price, amount in depth['bids']]
    asks = [(Decimal(price), Decimal(amount)) for price, amount in depth['asks']]

    # Средняя рыночная цена (mid price)
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = (best_bid + best_ask) / Decimal("2")

    # Границы диапазона (с конвертацией типов!)
    pct = Decimal(str(pct))  # если передаётся как float
    upper = mid_price * (Decimal("1") + pct)
    lower = mid_price * (Decimal("1") - pct)

    # Фильтрация по диапазону
    bids_in_range = [(price, qty) for price, qty in bids if lower <= price <= mid_price]
    asks_in_range = [(price, qty) for price, qty in asks if mid_price <= price <= upper]

    # Подсчёт объёмов и количества уровней
    bid_volume = sum(qty for _, qty in bids_in_range)
    ask_volume = sum(qty for _, qty in asks_in_range)
    bid_levels = len(bids_in_range)
    ask_levels = len(asks_in_range)

    # Пример возвращаемых данных
    return {
        "mid_price": float(mid_price),
        "lower": float(lower),
        "upper": float(upper),
        "bid_volume": float(bid_volume),
        "ask_volume": float(ask_volume),
        "bid_levels": bid_levels,
        "ask_levels": ask_levels,
        "top_bid": float(bids_in_range[0][0]) if bid_levels > 0 else None,
        "top_ask": float(asks_in_range[0][0]) if ask_levels > 0 else None,
    }

# Пример вызова:
stats = get_orderbook_stats("BTCUSDT", pct=0.005)  # 0.5% диапазон
print(stats)
