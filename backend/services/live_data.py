"""
JARVIS — Live Data Service
Weather, News, Cricket, Crypto, Currency, Stocks, Flights, URL Summary, Web Search.
All calls are async (httpx) with 5s timeouts and graceful fallbacks.
"""
import re
import asyncio
from typing import Optional
import httpx
from backend import config

HEADERS = {"User-Agent": "Mozilla/5.0 JARVIS/1.0"}
TIMEOUT = 5.0

# ── Simple in-memory TTL cache ────────────────────────────
_cache: dict = {}


def _cache_get(key: str) -> Optional[str]:
    import time
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["value"]
    return None


def _cache_set(key: str, value: str, ttl_seconds: int) -> None:
    import time
    _cache[key] = {"value": value, "expires": time.time() + ttl_seconds}


# ══════════════════════════════════════════════════════════
#  WEATHER
# ══════════════════════════════════════════════════════════

async def get_weather(lat: float = 17.385, lon: float = 78.4867, city: str = "Hyderabad") -> str:
    cached = _cache_get(f"weather_{lat}_{lon}")
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as http:
            r = await http.get(
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,weathercode,windspeed_10m,relative_humidity_2m"
                f"&timezone=auto"
            )
            d = r.json()["current"]
            codes = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Foggy", 61: "Light rain", 63: "Moderate rain",
                80: "Rain showers", 95: "Thunderstorm"
            }
            result = (
                f"{city}: {codes.get(d['weathercode'], 'Unknown')}, "
                f"{d['temperature_2m']}°C, "
                f"Humidity {d['relative_humidity_2m']}%, "
                f"Wind {d['windspeed_10m']} km/h"
            )
            _cache_set(f"weather_{lat}_{lon}", result, 600)  # 10 min TTL
            return result
    except Exception as e:
        return f"Weather unavailable right now. ({e})"


# ══════════════════════════════════════════════════════════
#  NEWS
# ══════════════════════════════════════════════════════════

async def get_world_news(query: str = "") -> str:
    cache_key = f"news_{query}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    all_titles = []
    feeds = [
        "https://feeds.bbcnews.com/news/world/rss.xml",
        "https://rss.cnn.com/rss/edition_world.rss",
    ]

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
        for url in feeds:
            try:
                r = await http.get(url)
                titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
                if not titles:
                    titles = re.findall(r'<title>(.*?)</title>', r.text)
                clean = [
                    t.strip() for t in titles
                    if len(t.strip()) > 20
                    and not any(x in t for x in ["BBC", "CNN", "RSS", "World"])
                ][:3]
                all_titles.extend(clean)
            except:
                continue

        if query:
            try:
                r = await http.get(
                    f"https://api.duckduckgo.com/?q={query}+latest+news&format=json&no_html=1"
                )
                d = r.json()
                if d.get("AbstractText") and len(d["AbstractText"]) > 50:
                    all_titles.insert(0, d["AbstractText"][:400])
            except:
                pass

    result = ("LIVE NEWS:\n" + "\n".join(f"• {t}" for t in all_titles[:6])
              if all_titles else "News unavailable.")
    _cache_set(cache_key, result, 900)  # 15 min TTL
    return result


# ══════════════════════════════════════════════════════════
#  CRICKET
# ══════════════════════════════════════════════════════════

async def get_cricket_scores() -> str:
    cached = _cache_get("cricket")
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
            r = await http.get(
                "https://api.duckduckgo.com/?q=cricket+live+score+today+India&format=json&no_html=1"
            )
            d = r.json()
            results = []
            if d.get("AbstractText"):
                results.append(d["AbstractText"][:300])
            for t in d.get("RelatedTopics", [])[:4]:
                if isinstance(t, dict) and t.get("Text") and "score" in t["Text"].lower():
                    results.append(t["Text"][:200])
            result = ("CRICKET:\n" + "\n".join(f"• {r}" for r in results)
                      if results else "No live cricket matches found.")
            _cache_set("cricket", result, 120)  # 2 min TTL
            return result
    except Exception as e:
        return f"Cricket scores unavailable. ({e})"


# ══════════════════════════════════════════════════════════
#  CRYPTO
# ══════════════════════════════════════════════════════════

async def get_crypto_prices(coins: str = "bitcoin,ethereum,dogecoin") -> str:
    cached = _cache_get(f"crypto_{coins}")
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
            r = await http.get(
                f"https://api.coingecko.com/api/v3/simple/price"
                f"?ids={coins}&vs_currencies=inr,usd"
            )
            d = r.json()
            names = {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "dogecoin": "Dogecoin"}
            lines = []
            for k, v in d.items():
                lines.append(
                    f"{names.get(k, k)}: ₹{v.get('inr', 0):,.0f} / ${v.get('usd', 0):,.2f}"
                )
            result = ("CRYPTO PRICES:\n" + "\n".join(lines) if lines else "Crypto prices unavailable.")
            _cache_set(f"crypto_{coins}", result, 120)  # 2 min TTL
            return result
    except Exception as e:
        return f"Crypto prices unavailable. ({e})"


# ══════════════════════════════════════════════════════════
#  CURRENCY
# ══════════════════════════════════════════════════════════

async def get_currency_rate(
    from_c: str = "USD", to_c: str = "INR", amount: float = 1
) -> str:
    cache_key = f"fx_{from_c}_{to_c}"
    cached = _cache_get(cache_key)
    if cached:
        # Recompute with the requested amount even if rate was cached
        try:
            rate = float(cached)
            return f"{amount} {from_c} = {rate * amount:.2f} {to_c}"
        except:
            pass
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as http:
            r = await http.get(f"https://api.frankfurter.app/latest?from={from_c}&to={to_c}")
            d = r.json()
            rate = d["rates"].get(to_c, 0)
            _cache_set(cache_key, str(rate), 600)
            return f"{amount} {from_c} = {rate * amount:.2f} {to_c} (Rate: {rate:.4f})"
    except Exception as e:
        return f"Currency conversion unavailable. ({e})"


# ══════════════════════════════════════════════════════════
#  STOCKS
# ══════════════════════════════════════════════════════════

async def get_stock_price(symbol: str = "RELIANCE") -> str:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
            r = await http.get(
                f"https://api.duckduckgo.com/?q={symbol}+NSE+stock+price+today&format=json&no_html=1"
            )
            d = r.json()
            if d.get("AbstractText"):
                return f"STOCK INFO ({symbol}):\n{d['AbstractText'][:300]}"
            return f"Could not find live price for {symbol}. Check NSE/BSE directly."
    except Exception as e:
        return f"Stock lookup failed. ({e})"


# ══════════════════════════════════════════════════════════
#  FLIGHTS
# ══════════════════════════════════════════════════════════

async def get_flight_status(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
            r = await http.get(
                f"https://api.duckduckgo.com/?q={query}+flight+status+live&format=json&no_html=1"
            )
            d = r.json()
            if d.get("AbstractText"):
                return f"FLIGHT INFO:\n{d['AbstractText'][:400]}"
            return "Flight status not found. Please check the airline website directly."
    except Exception as e:
        return f"Flight lookup failed. ({e})"


# ══════════════════════════════════════════════════════════
#  URL SUMMARIZER
# ══════════════════════════════════════════════════════════

async def summarize_url(url: str) -> str:
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        async with httpx.AsyncClient(timeout=8, headers=HEADERS,
                                      follow_redirects=True) as http:
            r = await http.get(url)
            text = re.sub(r'<[^>]+>', ' ', r.text)
            text = re.sub(r'\s+', ' ', text).strip()[:4000]

        resp = client.chat.completions.create(
            model=config.MODEL_FAST,
            messages=[
                {"role": "system", "content": "Summarize this web page in 3-5 clear sentences. Extract key information only."},
                {"role": "user", "content": text}
            ],
            max_tokens=250
        )
        return "URL SUMMARY:\n" + resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not summarize URL. ({e})"


# ══════════════════════════════════════════════════════════
#  WEB SEARCH
# ══════════════════════════════════════════════════════════

async def web_search(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
            r = await http.get(
                f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            )
            d = r.json()
            if d.get("AbstractText"):
                return d["AbstractText"]
            topics = [
                t["Text"] for t in d.get("RelatedTopics", [])[:3]
                if isinstance(t, dict) and t.get("Text")
            ]
            return "\n".join(topics) if topics else "No results found."
    except Exception as e:
        return f"Search failed. ({e})"


# ══════════════════════════════════════════════════════════
#  IMAGE ANALYSIS
# ══════════════════════════════════════════════════════════

async def analyze_image(base64_img: str, prompt: str = "Describe this image in detail.") -> str:
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=config.MODEL_VISION,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
                {"type": "text", "text": prompt}
            ]}],
            max_tokens=400
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Image analysis failed. ({e})"
