import httpx
import asyncio
from backend.config import config

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=8.0)
    return _client

async def get_weather(city: str = "Hyderabad") -> str:
    try:
        url = f"https://wttr.in/{city}?format=3"
        r = await _get_client().get(url)
        return f"Weather in {city}: {r.text.strip()}"
    except Exception as e:
        return f"Weather unavailable right now."

async def get_crypto_prices() -> str:
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,dogecoin&vs_currencies=inr,usd"
        r = await _get_client().get(url)
        data = r.json()
        lines = []
        for coin, name in [("bitcoin","BTC"),("ethereum","ETH"),("dogecoin","DOGE")]:
            if coin in data:
                inr = data[coin].get("inr","?")
                usd = data[coin].get("usd","?")
                lines.append(f"{name}: ₹{inr:,} (${usd})")
        return "Crypto prices: " + " | ".join(lines)
    except Exception:
        return "Crypto prices unavailable right now."

async def get_currency_rate(from_currency: str, to_currency: str, amount: float = 1.0) -> str:
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        r = await _get_client().get(url)
        data = r.json()
        rate = data["rates"].get(to_currency)
        if rate:
            converted = amount * rate
            return f"{amount} {from_currency} = {converted:.2f} {to_currency}"
        return f"Exchange rate for {from_currency} to {to_currency} unavailable."
    except Exception:
        return f"Currency conversion unavailable right now."

async def get_cricket_scores() -> str:
    try:
        url = "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/live"
        return "Cricket scores: Check cricbuzz.com for live scores."
    except Exception:
        return "Cricket scores unavailable. Check cricbuzz.com"

async def get_world_news(query: str = "") -> str:
    try:
        url = "https://gnews.io/api/v4/top-headlines?lang=en&country=in&max=3&apikey=demo"
        r = await _get_client().get(url)
        data = r.json()
        articles = data.get("articles", [])[:3]
        if articles:
            headlines = [a["title"] for a in articles]
            return "Latest news: " + " | ".join(headlines)
        return "Check Google News or NDTV for latest headlines."
    except Exception:
        return "News unavailable right now. Check news.google.com"

async def get_stock_price(symbol: str = "NIFTY") -> str:
    return f"For {symbol} stock price, check NSE India (nseindia.com) or moneycontrol.com"

async def summarize_url(url: str) -> str:
    try:
        r = await _get_client().get(url, follow_redirects=True)
        text = r.text[:3000]
        import re
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()[:500]
        return f"From that URL: {text}..."
    except Exception:
        return f"Could not fetch content from that URL."

async def _gather_tool_data(text: str, lower: str) -> list:
    from backend.services import command_parser
    tasks = []
    labels = []

    if command_parser.is_weather_query(text):
        tasks.append(get_weather())
        labels.append("weather")

    if command_parser.is_news_query(text):
        tasks.append(get_world_news(text))
        labels.append("news")

    if command_parser.is_cricket_query(text):
        tasks.append(get_cricket_scores())
        labels.append("cricket")

    if command_parser.is_crypto_query(text):
        tasks.append(get_crypto_prices())
        labels.append("crypto")

    is_fx, from_c, to_c, amount = command_parser.is_currency_query(text)
    if is_fx:
        tasks.append(get_currency_rate(from_c, to_c, amount))
        labels.append("currency")

    if command_parser.is_stock_query(text):
        tasks.append(get_stock_price())
        labels.append("stock")

    url = command_parser.is_url(text)
    if url:
        tasks.append(summarize_url(url))
        labels.append("url")

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            continue
        output.append(f"[{label.upper()}] {result}")
    return output
