import feedparser

# Ключевые слова для фильтрации новостей
KEYWORDS = ['btc', 'bitcoin', 'eth', 'ethereum', 'etf', 'crypto', 'trump', 'blackrock', 'sec', 'halving', 'spot', 'approval']

# Храним уже отправленные заголовки, чтобы не было повторов
already_sent_titles = set()

def fetch_coindesk_news(force_all=False):
    print("📡 Чтение новостей из CoinDesk...")
    feed_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    feed = feedparser.parse(feed_url)

    filtered = []
    for entry in feed.entries:
        published = entry.get("published", "")
        title = entry.get("title", "")
        link = entry.get("link", "")
        print(f"→ Проверка: {title}")

        if any(keyword.lower() in title.lower() for keyword in KEYWORDS):
            if force_all or title not in already_sent_titles:
                print(f"✅ Добавлено: {title}")
                filtered.append({
                    "title": title,
                    "link": link,
                    "published": published
                })
                already_sent_titles.add(title)
            else:
                print(f"⚠️ Пропущено (уже отправлено): {title}")
        else:
            print(f"❌ Пропущено (нет ключевых слов): {title}")
    return filtered

def fetch_crypto_panic_news():
    # Здесь можно подключить API позже
    return []

def fetch_all_news(force_all=False):
    print("⏰ Проверка новостей по всем источникам...")
    news = fetch_coindesk_news(force_all=force_all) + fetch_crypto_panic_news()
    print(f"🗞 Всего подходящих новостей: {len(news)}")
    return news

def format_news_message(item):
    return (
        f"📰 <b>{item['title']}</b>\n"
        f"🗓 <i>{item['published']}</i>\n"
        f"🔗 <a href='{item['link']}'>Читать</a>"
    )
