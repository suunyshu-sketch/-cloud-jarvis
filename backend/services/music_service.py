"""
JARVIS — Music Service
iTunes Preview API search + queue management helpers.
"""
import httpx
import re
from typing import Optional

TIMEOUT = 6.0
HEADERS = {"User-Agent": "JARVIS/2.0"}


async def search_music(query: str, limit: int = 8) -> list:
    """
    Search iTunes for tracks.
    Returns list of {title, artist, preview_url, artwork, track_id, duration}.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as http:
            r = await http.get(
                "https://itunes.apple.com/search",
                params={
                    "term": query,
                    "media": "music",
                    "entity": "song",
                    "limit": limit,
                    "country": "IN",
                }
            )
            data = r.json()
            results = []
            for item in data.get("results", []):
                if not item.get("previewUrl"):
                    continue
                results.append({
                    "track_id":    item.get("trackId", ""),
                    "title":       item.get("trackName", "Unknown"),
                    "artist":      item.get("artistName", "Unknown"),
                    "album":       item.get("collectionName", ""),
                    "preview_url": item.get("previewUrl", ""),
                    "artwork":     item.get("artworkUrl100", "").replace("100x100", "300x300"),
                    "duration_ms": item.get("trackTimeMillis", 30000),
                    "genre":       item.get("primaryGenreName", ""),
                })
            return results
    except Exception as e:
        print(f"music search error: {e}")
        return []


async def search_music_by_genre(genre: str, limit: int = 6) -> list:
    """Get popular songs by genre from iTunes."""
    genre_queries = {
        "bollywood":  "bollywood hits 2024",
        "telugu":     "telugu songs 2024",
        "tamil":      "tamil hits 2024",
        "lofi":       "lofi chill beats",
        "devotional": "hindu devotional songs",
        "classical":  "carnatic classical music",
        "pop":        "top pop hits 2024",
        "romantic":   "romantic hindi songs",
    }
    query = genre_queries.get(genre.lower(), genre)
    return await search_music(query, limit)


def get_youtube_url(query: str) -> str:
    """Generate YouTube search URL for a song."""
    encoded = query.replace(" ", "+")
    return f"https://www.youtube.com/results?search_query={encoded}"


def parse_music_command(text: str) -> Optional[dict]:
    """
    Returns {"type": "search"|"genre", "query": str} or None.
    Handles: 'play Nadaniya', 'play some lofi music', 'play telugu songs'
    """
    lower = text.lower().strip()
    m = re.search(r'\b(?:play|listen to|put on|queue)\s+(.+)', lower)
    if not m:
        return None

    query = m.group(1).strip()
    genres = ["bollywood", "telugu", "tamil", "lofi", "devotional", "classical", "pop", "romantic"]

    # Check if it's a genre request
    for g in genres:
        if g in query or f"{g} music" in query or f"{g} songs" in query:
            return {"type": "genre", "query": g}

    return {"type": "search", "query": query}
