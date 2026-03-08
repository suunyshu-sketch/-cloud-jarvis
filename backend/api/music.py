"""
JARVIS — Music API Routes
"""
from fastapi import APIRouter, Depends, Query
from backend.middleware.auth_guard import require_auth
from backend.services.music_service import search_music, search_music_by_genre, get_youtube_url

router = APIRouter(prefix="/music", tags=["music"])


@router.get("/search")
async def search(q: str = Query(..., min_length=1), user=Depends(require_auth)):
    results = await search_music(q, limit=8)
    return {"results": results, "youtube": get_youtube_url(q)}


@router.get("/genre/{genre}")
async def by_genre(genre: str, user=Depends(require_auth)):
    results = await search_music_by_genre(genre, limit=6)
    return {"results": results, "genre": genre}
