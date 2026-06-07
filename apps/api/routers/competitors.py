from __future__ import annotations
import time
import unicodedata
import requests
from fastapi import APIRouter, HTTPException
from config import GOOGLE_API_KEY

router = APIRouter()

_cache: list[dict] | None = None


@router.get("/api/competitors")
def get_competitors(lat: float = 33.45, lng: float = -112.0, radius_miles: float = 30.0):
    global _cache
    if _cache is not None:
        return {"competitors": _cache, "count": len(_cache)}

    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    def _norm(s: str) -> str:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

    radius_m = min(int(radius_miles * 1609.34), 50000)
    all_results: list[dict] = []
    page_token: str | None = None

    for _ in range(3):
        params: dict = {
            "query": "gym OR fitness center OR health club",
            "location": f"{lat},{lng}",
            "radius": radius_m,
            "key": GOOGLE_API_KEY,
        }
        if page_token:
            params["pagetoken"] = page_token
            time.sleep(2)

        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params=params,
                timeout=15,
            )
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Places API error: {e}")

        for place in data.get("results", []):
            name = place.get("name", "")
            if "eos fitness" in _norm(name):
                continue
            loc = place.get("geometry", {}).get("location", {})
            if loc.get("lat") and loc.get("lng"):
                all_results.append({
                    "name":   name,
                    "lat":    loc["lat"],
                    "lng":    loc["lng"],
                    "rating": place.get("rating"),
                })

        page_token = data.get("next_page_token")
        if not page_token:
            break

    _cache = all_results
    return {"competitors": all_results, "count": len(all_results)}
