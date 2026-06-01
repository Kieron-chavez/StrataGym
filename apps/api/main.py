import csv
import math
import os
import time
import unicodedata
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

REPO_ROOT = Path(__file__).parent.parent.parent
load_dotenv(REPO_ROOT / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

_competitors_cache: list[dict] | None = None

app = FastAPI(title="StrataGym API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GYM_MASTER_PATH = REPO_ROOT / "ml" / "data" / "raw" / "eos_locations.csv"


def _city_from_address(address: str) -> str:
    parts = [p.strip() for p in address.split(",")]
    return parts[1] if len(parts) >= 3 else "Arizona"


def _build_name(address: str, city_counts: dict[str, int], city_seen: dict[str, int]) -> str:
    city = _city_from_address(address)
    city_seen[city] = city_seen.get(city, 0) + 1
    if city_counts.get(city, 1) > 1:
        return f"EOS Fitness – {city} #{city_seen[city]}"
    return f"EOS Fitness – {city}"


def load_gyms() -> list[dict]:
    if not GYM_MASTER_PATH.exists():
        raise RuntimeError(f"eos_locations.csv not found. Run ml/scripts/01_pull_eos_locations.py first.")

    rows = []
    with open(GYM_MASTER_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    city_counts: dict[str, int] = {}
    for row in rows:
        city = _city_from_address(row.get("address", ""))
        city_counts[city] = city_counts.get(city, 0) + 1

    city_seen: dict[str, int] = {}
    gyms = []
    for row in rows:
        address = row.get("address", "")
        gyms.append({
            "gym_id":           row["gym_id"],
            "name":             _build_name(address, city_counts, city_seen),
            "address":          address,
            "lat":              float(row["latitude"]),
            "lng":              float(row["longitude"]),
            "status":           row.get("status", "open"),
            "monthly_members":  int(row["monthly_members"] or 0),
            "monthly_checkins": int(row["monthly_checkins"] or 0),
            "rating":           float(row["rating"]) if row.get("rating") else None,
            "review_count":     int(row["review_count"]) if row.get("review_count") else None,
        })
    return gyms


GYMS = load_gyms()


class ScoreRequest(BaseModel):
    lat: float
    lng: float


@app.get("/api/gyms")
def get_gyms():
    return {"gyms": GYMS}


@app.post("/api/score-location")
def score_location(body: ScoreRequest):
    def _dist(g: dict) -> float:
        dlat = body.lat - g["lat"]
        dlng = body.lng - g["lng"]
        return math.sqrt(dlat**2 + (dlng * math.cos(math.radians(body.lat)))**2) * 69.0

    nearby = sorted(
        [{"gym_id": g["gym_id"], "name": g["name"], "lat": g["lat"], "lng": g["lng"],
          "distance_miles": round(_dist(g), 1)} for g in GYMS],
        key=lambda x: x["distance_miles"],
    )
    return {
        "lat": body.lat, "lng": body.lng,
        "opportunity_score": 82, "projected_checkins": 8760,
        "cannibalization_risk": 24, "net_network_impact": 5420,
        "nearby_gyms": nearby[:3],
    }


@app.get("/api/competitors")
def get_competitors(lat: float = 33.45, lng: float = -112.0, radius_miles: float = 30.0):
    global _competitors_cache
    if _competitors_cache is not None:
        return {"competitors": _competitors_cache, "count": len(_competitors_cache)}

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

    _competitors_cache = all_results
    return {"competitors": all_results, "count": len(all_results)}


@app.get("/api/census-density")
def get_census_density():
    census_path    = REPO_ROOT / "ml" / "data" / "raw" / "census_tracts_combined.csv"
    centroids_path = REPO_ROOT / "ml" / "data" / "raw" / "tract_centroids_az.csv"

    if not census_path.exists() or not centroids_path.exists():
        raise HTTPException(status_code=404, detail="Census data not available")

    census    = pd.read_csv(census_path, dtype={"geoid": str})
    centroids = pd.read_csv(centroids_path, dtype={"geoid": str})

    merged = centroids.merge(
        census[["geoid", "total_population", "pct_age_18_34", "median_household_income"]],
        on="geoid", how="left",
    ).dropna(subset=["centroid_lat", "centroid_lon", "pct_age_18_34"])

    # NaN is truthy in Python — "nan or 0" returns nan, and int(nan) throws ValueError
    merged = merged.fillna({"total_population": 0, "median_household_income": 0})

    tracts = [
        {
            "lat":           round(float(row.centroid_lat), 6),
            "lng":           round(float(row.centroid_lon), 6),
            "population":    int(row.total_population),
            "pct_age_18_34": round(float(row.pct_age_18_34), 4),
            "median_income": int(row.median_household_income),
        }
        for row in merged.itertuples()
    ]

    return {"tracts": tracts, "count": len(tracts)}
