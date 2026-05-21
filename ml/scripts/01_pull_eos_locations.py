# =============================================================================
# scripts/01_pull_eos_locations.py
#
# Searches Google Places for every real EOS Fitness location in Arizona.
# Uses a Text Search sweep across sub-regions to avoid the 60-result
# per-query cap, then deduplicates by place_id.
#
# Output:
#   data/raw/eos_locations.csv
#
# Run ONCE — saves output, skips on re-run.
#
# Requires: GOOGLE_API_KEY in StrataGym/.env (Places API enabled)
# Cost: ~$0.05  (handful of Text Search calls)
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import requests
import pandas as pd
import time
from dotenv import load_dotenv
from config.config import *

load_dotenv(Path(__file__).parent.parent.parent / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"

# Sweep centers to cover the full AZ metro area — avoids the 60-result cap
# (Phoenix metro alone has 20+ EOS locations)
AZ_SEARCH_CENTERS = [
    ("Phoenix NW",   33.5722, -112.0901, 25000),
    ("Phoenix SE",   33.3600, -111.9200, 25000),
    ("Scottsdale",   33.4942, -111.9261, 20000),
    ("East Valley",  33.3750, -111.7500, 30000),
    ("West Valley",  33.5200, -112.3500, 35000),
    ("Tucson",       32.2226, -110.9747, 40000),
    ("Flagstaff",    35.1983, -111.6513, 50000),
]


def text_search_page(query: str, location: str, radius: int,
                     page_token: str = None) -> dict:
    params = {
        "query":    query,
        "location": location,
        "radius":   radius,
        "key":      GOOGLE_API_KEY,
    }
    if page_token:
        params = {"pagetoken": page_token, "key": GOOGLE_API_KEY}

    resp = requests.get(TEXT_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_place_details(place_id: str) -> dict:
    """Fetch phone + website for richer data."""
    params = {
        "place_id": place_id,
        "fields":   "name,formatted_address,geometry,formatted_phone_number,website,opening_hours,rating,user_ratings_total",
        "key":      GOOGLE_API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", {})


def search_region(label: str, lat: float, lon: float, radius_m: int) -> list[dict]:
    """Return all EOS Fitness places in a region."""
    location = f"{lat},{lon}"
    query    = "EOS Fitness"
    results  = []
    token    = None
    page     = 0

    print(f"  [{label}] searching...")

    while page < 3:  # max 3 pages = 60 results
        data  = text_search_page(query, location, radius_m, token)
        batch = data.get("results", [])
        results.extend(batch)

        token = data.get("next_page_token")
        page += 1
        if not token:
            break
        time.sleep(2.5)  # token needs ~2s to activate

    # Filter to EOS only — normalize Unicode (EōS → eos) before matching
    import unicodedata
    def _norm(s: str) -> str:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

    eos = [r for r in results if "eos fitness" in _norm(r.get("name", ""))]
    print(f"    → {len(results)} results, {len(eos)} EOS Fitness")
    return eos


def parse_place(place: dict) -> dict:
    loc     = place.get("geometry", {}).get("location", {})
    address = place.get("formatted_address", "")

    # Extract city from address: "123 Main St, Chandler, AZ 85224, USA"
    parts = [p.strip() for p in address.split(",")]
    city  = parts[1] if len(parts) >= 3 else "Arizona"

    return {
        "place_id":   place.get("place_id", ""),
        "gym_name":   place.get("name", ""),
        "address":    address,
        "city":       city,
        "latitude":   loc.get("lat"),
        "longitude":  loc.get("lng"),
        "rating":     place.get("rating"),
        "review_count": place.get("user_ratings_total"),
    }


def build_gym_master(places: list[dict]) -> pd.DataFrame:
    rows = []
    for i, p in enumerate(places, start=1):
        gym_id = f"eos-az-{i:03d}"
        rows.append({
            "gym_id":             gym_id,
            "gym_name":           p["gym_name"],
            "cluster":            p["city"],
            "address":            p["address"],
            "latitude":           p["latitude"],
            "longitude":          p["longitude"],
            "rating":             p.get("rating"),
            "review_count":       p.get("review_count"),
            "square_footage":     None,   # not available from Places API
            "tier":               None,
            "monthly_dues_base":  None,
            "amenities":          None,
            "grand_opening_date": None,
            "status":             "open",
            "monthly_checkins":   0,
            "monthly_members":    0,
        })
    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("EOS Fitness Locations — Google Places Pull")
    print("=" * 60)

    if not GOOGLE_API_KEY:
        print("\n✗ ERROR: GOOGLE_API_KEY not set.")
        print("  Create StrataGym/.env with:")
        print("    GOOGLE_API_KEY=your_key_here")
        sys.exit(1)

    out_path = DATA_RAW / "eos_locations.csv"
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        print(f"\n✓ eos_locations.csv already exists ({out_path}).")
        print("  Delete it to re-pull.")
        df = pd.read_csv(out_path)
        print(f"  {len(df)} EOS locations loaded.")
        print(df[["gym_id", "gym_name", "latitude", "longitude"]].to_string(index=False))
        return df

    # ── Sweep all regions ─────────────────────────────────────────────────────
    all_places: dict[str, dict] = {}   # place_id → parsed place

    for label, lat, lon, radius in AZ_SEARCH_CENTERS:
        raw = search_region(label, lat, lon, radius)
        for place in raw:
            pid = place.get("place_id", "")
            if pid and pid not in all_places:
                all_places[pid] = parse_place(place)
        time.sleep(1)

    places = list(all_places.values())
    print(f"\n  Total unique EOS Fitness locations: {len(places)}")

    if len(places) == 0:
        print("\n✗ No results. Check that your API key has Places API enabled.")
        sys.exit(1)

    # Sort by city then name for consistent gym_ids
    places.sort(key=lambda p: (p["city"], p["gym_name"]))

    # ── Build gym_master ──────────────────────────────────────────────────────
    df = build_gym_master(places)
    df.to_csv(out_path, index=False)

    print(f"\n✓ Saved → {out_path}  ({len(df)} locations)")
    print(f"\n{'='*60}")
    print(df[["gym_id", "gym_name", "latitude", "longitude", "address"]].to_string(index=False))

    return df


if __name__ == "__main__":
    main()
