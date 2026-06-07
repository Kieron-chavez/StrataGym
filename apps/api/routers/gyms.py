from __future__ import annotations
import math
import hashlib
import cache
import pandas as pd
from fastapi import APIRouter, HTTPException
from config import REPO_ROOT
from store import GYMS

router = APIRouter()

TRADE_AREA_MILES = 5.0  # ~10-min drive proxy


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _get_census_tracts() -> list[dict]:
    if cache.census_tracts is not None:
        return cache.census_tracts

    census_path    = REPO_ROOT / "ml" / "data" / "raw" / "census_tracts_combined.csv"
    centroids_path = REPO_ROOT / "ml" / "data" / "raw" / "tract_centroids_az.csv"

    if not census_path.exists() or not centroids_path.exists():
        return []

    census    = pd.read_csv(census_path, dtype={"geoid": str})
    centroids = pd.read_csv(centroids_path, dtype={"geoid": str})
    age_col = "pct_age_25_44" if "pct_age_25_44" in census.columns else "pct_age_18_34"
    merged = centroids.merge(
        census[["geoid", "total_population", "median_age", "median_household_income", age_col]],
        on="geoid", how="left",
    ).dropna(subset=["centroid_lat", "centroid_lon", age_col])
    merged = merged.fillna({"total_population": 0, "median_household_income": 0, "median_age": 0})

    tracts = [
        {
            "lat":           float(row.centroid_lat),
            "lng":           float(row.centroid_lon),
            "population":    int(row.total_population),
            "pct_age_target": float(getattr(row, age_col)),
            "median_income":  int(row.median_household_income),
            "median_age":     float(row.median_age),
        }
        for row in merged.itertuples()
    ]
    cache.census_tracts = tracts
    return tracts


@router.get("/api/gyms")
def get_gyms():
    return {"gyms": GYMS}


@router.get("/api/gyms/{gym_id}/analysis")
def get_gym_analysis(gym_id: str):
    gym = next((g for g in GYMS if g["gym_id"] == gym_id), None)
    if not gym:
        raise HTTPException(status_code=404, detail="Gym not found")

    # Performance tier — actual rank within the network by monthly check-ins
    rank_pct = round(
        sum(1 for g in GYMS if g["monthly_checkins"] <= gym["monthly_checkins"]) / len(GYMS) * 100
    )
    tier = "Top Performer" if rank_pct >= 67 else "Average" if rank_pct >= 34 else "Underperforming"

    # Open date — deterministic pseudo data seeded by gym_id
    h = int(hashlib.md5(gym_id.encode()).hexdigest()[:8], 16)
    open_year  = 2010 + (h % 13)
    open_month = 1 + ((h >> 4) % 12)

    # Real trade area demographics — census tracts within TRADE_AREA_MILES
    tracts = _get_census_tracts()
    in_trade = [
        t for t in tracts
        if _haversine_miles(gym["lat"], gym["lng"], t["lat"], t["lng"]) <= TRADE_AREA_MILES
    ]
    total_pop = sum(t["population"] for t in in_trade)
    if total_pop > 0:
        w_income    = sum(t["median_income"]    * t["population"] for t in in_trade) / total_pop
        w_age_pct   = sum(t["pct_age_target"]   * t["population"] for t in in_trade) / total_pop
        w_median_age = sum(t["median_age"]      * t["population"] for t in in_trade) / total_pop
    else:
        w_income = w_age_pct = w_median_age = 0

    # Nearby EOS locations (real distances)
    nearby_eos = sorted(
        [
            {
                "gym_id":         g["gym_id"],
                "name":           g["name"],
                "distance_miles": round(_haversine_miles(gym["lat"], gym["lng"], g["lat"], g["lng"]), 1),
            }
            for g in GYMS if g["gym_id"] != gym_id
        ],
        key=lambda x: x["distance_miles"],
    )[:5]

    # Nearby competitors (available once /api/competitors has been called)
    nearby_competitors: list[dict] = []
    if cache.competitors:
        with_dist = [
            {
                "name":           c["name"],
                "lat":            c["lat"],
                "lng":            c["lng"],
                "rating":         c.get("rating"),
                "distance_miles": round(_haversine_miles(gym["lat"], gym["lng"], c["lat"], c["lng"]), 1),
            }
            for c in cache.competitors
        ]
        nearby_competitors = sorted(with_dist, key=lambda x: x["distance_miles"])[:5]

    return {
        "gym_id":               gym_id,
        "open_date":            f"{open_year}-{open_month:02d}",
        "performance_tier":     tier,
        "performance_rank_pct": rank_pct,
        "trade_area": {
            "population":    total_pop,
            "median_income": round(w_income),
            "median_age":    round(w_median_age, 1),
        },
        "nearby_eos":         nearby_eos,
        "nearby_competitors": nearby_competitors,
    }
