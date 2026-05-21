# =============================================================================
# scripts/pull_google_places.py
#
# For each of the 42 synthetic gyms, pulls from Google Places API:
#   - Competing gyms within 3mi and 5mi
#   - Grocery stores, restaurants, retail within 1mi
#   - Schools within 2mi
#   - Apartment complexes within 2mi
#
# PULL ONCE — saves to:
#   data/raw/competitors_per_gym.csv
#   data/raw/pois_per_gym.csv
#
# COMMIT both files to GitHub. Your partner never runs this.
#
# Cost: ~$12-18 total for all 42 gyms (covered by Google's $200/mo free credit)
# Time: ~8-10 minutes (rate limited to be safe)
#
# Requires: Google Maps API key with Places API enabled
#   https://console.cloud.google.com/google/maps-apis
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import os
import pandas as pd
import time
import json
from dotenv import load_dotenv
from config.config import *

load_dotenv(Path(__file__).parent.parent.parent / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_KEY_HERE")

PLACES_NEARBY_URL  = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_TEXT_URL    = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# Boutique fitness to exclude from competitor count
BOUTIQUE_KEYWORDS = [
    "yoga", "pilates", "barre", "spin studio", "cycling studio",
    "dance", "ballet", "martial arts", "karate", "jiu jitsu",
    "boxing", "kickboxing", "zumba",
]

EOS_KEYWORDS = ["eos fitness", "eos fitness"]


def is_boutique(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in BOUTIQUE_KEYWORDS)


def is_self(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in EOS_KEYWORDS)


def places_nearby(lat, lon, radius_m, place_type, api_key, retries=3):
    """Single Places Nearby Search call with pagination."""
    params = {
        "location": f"{lat},{lon}",
        "radius":   radius_m,
        "type":     place_type,
        "key":      api_key,
    }
    results = []

    for attempt in range(retries):
        try:
            resp = requests.get(PLACES_NEARBY_URL, params=params, timeout=15)
            data = resp.json()

            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return results

            results.extend(data.get("results", []))

            # Handle pagination (up to 60 results)
            token = data.get("next_page_token")
            pages = 0
            while token and pages < 2:
                time.sleep(2)  # token needs ~2s to activate
                page_resp = requests.get(
                    PLACES_NEARBY_URL,
                    params={"pagetoken": token, "key": api_key},
                    timeout=15,
                )
                page_data = page_resp.json()
                results.extend(page_data.get("results", []))
                token = page_data.get("next_page_token")
                pages += 1

            return results

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"      ✗ Places error: {e}")
                return results

    return results


def places_text_search(lat, lon, radius_m, query, api_key, retries=3):
    """Text search for gyms and apartments."""
    params = {
        "query":    query,
        "location": f"{lat},{lon}",
        "radius":   radius_m,
        "key":      api_key,
    }
    results = []

    for attempt in range(retries):
        try:
            resp = requests.get(PLACES_TEXT_URL, params=params, timeout=15)
            data = resp.json()

            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return results

            results.extend(data.get("results", []))

            token = data.get("next_page_token")
            pages = 0
            while token and pages < 2:
                time.sleep(2)
                page_resp = requests.get(
                    PLACES_TEXT_URL,
                    params={"pagetoken": token, "key": api_key},
                    timeout=15,
                )
                page_data = page_resp.json()
                results.extend(page_data.get("results", []))
                token = page_data.get("next_page_token")
                pages += 1

            return results

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"      ✗ Text search error: {e}")
                return results

    return results


def pull_competitors_for_gym(gym_id, lat, lon, api_key):
    """Pull and filter competing gyms at 3mi and 5mi."""
    row = {"gym_id": gym_id}

    for label, radius_m in [("3mi", 4828), ("5mi", 8047)]:
        raw = places_text_search(
            lat, lon, radius_m,
            "gym OR fitness center OR health club",
            api_key
        )

        all_names     = [r.get("name", "") for r in raw]
        filtered      = [n for n in all_names if not is_boutique(n) and not is_self(n)]
        boutique_count = len([n for n in all_names if is_boutique(n)])

        row[f"competitor_count_{label}"]        = len(filtered)
        row[f"boutique_count_{label}"]          = boutique_count
        row[f"total_fitness_count_{label}"]     = len(raw)
        row[f"competitor_names_{label}"]        = "|".join(filtered[:10])  # top 10

        time.sleep(0.5)

    return row


def pull_pois_for_gym(gym_id, lat, lon, api_key):
    """Pull POI counts for retail density and apartment signals."""
    row = {"gym_id": gym_id}

    poi_pulls = [
        # (column_prefix, radius_m, search_type_or_query, is_text_search)
        ("grocery_count_1mi",    1609,  "grocery_or_supermarket",   False),
        ("restaurant_count_1mi", 1609,  "restaurant",               False),
        ("clothing_count_1mi",   1609,  "clothing_store",           False),
        ("mall_count_1mi",       1609,  "shopping_mall",            False),
        ("school_count_2mi",     3219,  "school",                   False),
        ("apartment_count_2mi",  3219,  "apartment complex",        True),
    ]

    for col, radius_m, query, is_text in poi_pulls:
        if is_text:
            results = places_text_search(lat, lon, radius_m, query, api_key)
        else:
            results = places_nearby(lat, lon, radius_m, query, api_key)

        row[col] = len(results)
        time.sleep(0.3)

    # Derived scores
    row["retail_density_score"] = round(
        (row["grocery_count_1mi"] * 0.3 +
         row["restaurant_count_1mi"] * 0.1 +
         row["clothing_count_1mi"] * 0.3 +
         row["mall_count_1mi"] * 1.0) / 10,
        4
    )

    return row


def main():
    print("=" * 60)
    print("Google Places Pull — Competitors + POIs")
    print("=" * 60)

    if GOOGLE_API_KEY == "YOUR_GOOGLE_KEY_HERE":
        print("\n✗ ERROR: Paste your Google Maps API key into this script first.")
        print("  https://console.cloud.google.com/google/maps-apis")
        sys.exit(1)

    gym_master = pd.read_csv(DATA_SYNTHETIC / "gym_master.csv")
    print(f"\nLoaded {len(gym_master)} gyms")

    # ── Competitors ──────────────────────────────────────────────────────────
    comp_path = DATA_RAW / "competitors_per_gym.csv"
    if comp_path.exists():
        print(f"\n✓ Competitors already pulled — {comp_path} exists. Skipping.")
        comp_df = pd.read_csv(comp_path)
    else:
        print(f"\nPulling competitor data ({len(gym_master)} gyms × 2 radii)...")
        print("  Estimated cost: ~$4  |  Time: ~4 minutes")
        comp_rows = []

        for i, gym in gym_master.iterrows():
            print(f"  [{i+1:2d}/{len(gym_master)}] {gym['gym_id']} — {gym['gym_name']}")
            row = pull_competitors_for_gym(
                gym["gym_id"], gym["latitude"], gym["longitude"], GOOGLE_API_KEY
            )
            comp_rows.append(row)
            time.sleep(0.5)

        comp_df = pd.DataFrame(comp_rows)
        comp_df.to_csv(comp_path, index=False)
        print(f"\n✓ Saved → {comp_path}")

    # ── POIs ─────────────────────────────────────────────────────────────────
    poi_path = DATA_RAW / "pois_per_gym.csv"
    if poi_path.exists():
        print(f"\n✓ POIs already pulled — {poi_path} exists. Skipping.")
        poi_df = pd.read_csv(poi_path)
    else:
        print(f"\nPulling POI data ({len(gym_master)} gyms × 6 categories)...")
        print("  Estimated cost: ~$8  |  Time: ~6 minutes")
        poi_rows = []

        for i, gym in gym_master.iterrows():
            print(f"  [{i+1:2d}/{len(gym_master)}] {gym['gym_id']} — {gym['gym_name']}")
            row = pull_pois_for_gym(
                gym["gym_id"], gym["latitude"], gym["longitude"], GOOGLE_API_KEY
            )
            poi_rows.append(row)
            time.sleep(0.5)

        poi_df = pd.DataFrame(poi_rows)
        poi_df.to_csv(poi_path, index=False)
        print(f"\n✓ Saved → {poi_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    merged = comp_df.merge(poi_df, on="gym_id")
    print(f"\n{'='*60}")
    print(f"PULL COMPLETE")
    print(f"  Competitor data:  {comp_path.name}")
    print(f"  POI data:         {poi_path.name}")
    print(f"\nSample competitor counts (3mi):")
    print(merged[["gym_id", "competitor_count_3mi", "retail_density_score"]].head(8).to_string(index=False))
    print(f"\n✓ Commit data/raw/ to GitHub — your partner won't need to re-run this.")


if __name__ == "__main__":
    main()