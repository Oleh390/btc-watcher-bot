import requests
import feedparser

KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', 'eth', 'etf', 'sec', 'blackrock', 'trump',
    'cpi', 'inflation', 'fed', 'stablecoin', 'approval', 'china', 'fomc'
]

MAX_NEWS = 5

def fetch_coindesk_news():
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    feed = feedparser.parse(url)
    filtered = []
    for entry in feed.entries:
        if any(keyword.lower() in entry.title.lower() for keyword in KEYWORDS):
            filtered.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published
            })
    return filtered[:MAX_NEWS]

def fetch_crypto_panic_news():
    url = "https://cryptopanic.com/api/v1/posts/?auth_token=&kind=news"
    try:
        response = requests.get(url)
        data = response.json()
        filtered = []
        for item in data.get("results", []):
            if any(keyword.lower() in item['title'].lower() for keyword in KEYWORDS):
                filtered.append({
                    'title': item['title'],
                    'link': item['url'],
                    'published': item['published_at']
                })
        return filtered[:MAX_NEWS]
    except:
        return []

def fetch_all_news():
    news = fetch_coindesk_news() + fetch_crypto_panic_news()
    unique_titles = set()
    unique_news = []
    for item in news:
        if item['title'] not in unique_titles:
            unique_titles.add(item['title'])
            unique_news.append(item)
    return unique_news[:MAX_NEWS]

def format_news_message(item):
    return (
        f"🗞️ <b>{item['title']}</b>\n"
        f"📅 {item['published']}\n"
        f"🔗 <a href=\"{item['link']}\">Читать</a>"
    )
