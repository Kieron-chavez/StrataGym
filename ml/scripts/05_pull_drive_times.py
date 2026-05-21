# =============================================================================
# scripts/pull_drive_times.py
#
# Pulls real drive times between:
#   1. Every pair of EOS gyms (cannibalization — how close are we to ourselves?)
#   2. Each gym to nearby census tract centroids (15-min trade area definition)
#
# PULL ONCE — saves to:
#   data/raw/gym_to_gym_drive_times.csv
#   data/raw/gym_to_tract_drive_times.csv
#
# COMMIT both to GitHub.
#
# Cost: ~$45-55 total (covered by Google's $200/mo free credit)
#   - Gym-to-gym: 42×42 = 1,764 elements @ $5/1000 = ~$9
#   - Gym-to-tract: ~700 tracts × 42 gyms batched = ~$40
# Time: ~15 minutes
#
# Requires: Google Maps API key with Distance Matrix API enabled
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import pandas as pd
import os
import numpy as np
import time
import math
from dotenv import load_dotenv
from config.config import *

load_dotenv(Path(__file__).parent.parent.parent / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_KEY_HERE")

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
MAX_ORIGINS_PER_CALL = 10   # 10×10=100 elements — the API hard limit per request
MAX_DESTS_PER_CALL   = 10
TRADE_AREA_MINUTES   = 15
PREFILTER_MILES      = 15  # exclude tracts >15mi away before API call


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def call_distance_matrix(origins, destinations, api_key, retries=3):
    """
    Call Distance Matrix API.
    origins/destinations: list of "lat,lon" strings
    Returns raw elements list.
    """
    params = {
        "origins":      "|".join(origins),
        "destinations": "|".join(destinations),
        "mode":         "driving",
        "key":          api_key,
    }

    for attempt in range(retries):
        try:
            resp = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=30)
            data = resp.json()

            if data.get("status") != "OK":
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                print(f"  ✗ API error: {data.get('status')} — {data.get('error_message', '')}")
                return None

            return data

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  ✗ Request error: {e}")
                return None

    return None


def pull_gym_to_gym(gym_master: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """
    Pull drive times between every pair of gyms.
    Used to compute: nearest_brand_location_minutes and cannibalization risk.
    42×42 = 1,764 elements, batched in 25×25 chunks.
    """
    coords = [f"{row.latitude},{row.longitude}" for _, row in gym_master.iterrows()]
    gym_ids = gym_master["gym_id"].tolist()
    n = len(coords)

    rows = []
    chunk_size = MAX_ORIGINS_PER_CALL

    total_calls = math.ceil(n / chunk_size) ** 2
    call_num = 0

    for i_start in range(0, n, chunk_size):
        i_end = min(i_start + chunk_size, n)
        origins = coords[i_start:i_end]
        origin_ids = gym_ids[i_start:i_end]

        for j_start in range(0, n, chunk_size):
            j_end = min(j_start + chunk_size, n)
            dests = coords[j_start:j_end]
            dest_ids = gym_ids[j_start:j_end]

            call_num += 1
            print(f"  Call {call_num}/{total_calls} — "
                  f"gyms {i_start+1}:{i_end} → {j_start+1}:{j_end}")

            data = call_distance_matrix(origins, dests, api_key)
            if data is None:
                continue

            for oi, row_data in enumerate(data["rows"]):
                for di, element in enumerate(row_data["elements"]):
                    origin_id = origin_ids[oi]
                    dest_id   = dest_ids[di]

                    if origin_id == dest_id:
                        continue  # skip self

                    duration_min  = None
                    distance_mi   = None

                    if element.get("status") == "OK":
                        duration_min = round(element["duration"]["value"] / 60, 2)
                        distance_mi  = round(element["distance"]["value"] * 0.000621371, 3)

                    rows.append({
                        "origin_gym_id":  origin_id,
                        "dest_gym_id":    dest_id,
                        "drive_minutes":  duration_min,
                        "distance_miles": distance_mi,
                    })

            time.sleep(0.3)

    return pd.DataFrame(rows)


def pull_gym_to_tracts(gym_master: pd.DataFrame, tract_centroids: pd.DataFrame,
                       api_key: str) -> pd.DataFrame:
    """
    For each gym, find all census tract centroids within 15-min drive.
    Pre-filter to tracts within 15 miles straight-line to reduce API calls.
    Result defines each gym's trade area.
    """
    all_rows = []
    n_gyms   = len(gym_master)

    for gi, gym in gym_master.iterrows():
        print(f"  Gym {gi+1}/{n_gyms}: {gym['gym_id']}")

        # Pre-filter: only tracts within PREFILTER_MILES straight line
        tract_centroids["_dist_mi"] = tract_centroids.apply(
            lambda t: haversine_miles(
                gym["latitude"], gym["longitude"],
                t["centroid_lat"], t["centroid_lon"]
            ), axis=1
        )
        nearby = tract_centroids[
            tract_centroids["_dist_mi"] <= PREFILTER_MILES
        ].copy()

        print(f"    {len(nearby)} tracts within {PREFILTER_MILES}mi pre-filter")

        if len(nearby) == 0:
            continue

        # Batch the nearby tracts in chunks of MAX_DESTS_PER_CALL
        origin = [f"{gym['latitude']},{gym['longitude']}"]
        tract_geoids = nearby["geoid"].tolist()
        tract_lats   = nearby["centroid_lat"].tolist()
        tract_lons   = nearby["centroid_lon"].tolist()

        for batch_start in range(0, len(nearby), MAX_DESTS_PER_CALL):
            batch_end = min(batch_start + MAX_DESTS_PER_CALL, len(nearby))
            dest_coords  = [
                f"{tract_lats[k]},{tract_lons[k]}"
                for k in range(batch_start, batch_end)
            ]
            dest_geoids = tract_geoids[batch_start:batch_end]

            data = call_distance_matrix(origin, dest_coords, api_key)
            if data is None or not data.get("rows"):
                continue

            elements = data["rows"][0]["elements"]
            for k, element in enumerate(elements):
                duration_min = None
                if element.get("status") == "OK":
                    duration_min = round(element["duration"]["value"] / 60, 2)

                all_rows.append({
                    "gym_id":       gym["gym_id"],
                    "tract_geoid":  dest_geoids[k],
                    "drive_minutes": duration_min,
                    "in_trade_area": (
                        duration_min is not None and
                        duration_min <= TRADE_AREA_MINUTES
                    ),
                })

            time.sleep(0.25)

    return pd.DataFrame(all_rows)


def main():
    print("=" * 60)
    print("Google Distance Matrix Pull")
    print("=" * 60)

    if GOOGLE_API_KEY == "YOUR_GOOGLE_KEY_HERE":
        print("\n✗ ERROR: Paste your Google Maps API key into this script first.")
        sys.exit(1)

    gym_master = pd.read_csv(DATA_SYNTHETIC / "gym_master.csv")
    print(f"\nLoaded {len(gym_master)} gyms")

    # ── Gym-to-gym ────────────────────────────────────────────────────────────
    g2g_path = DATA_RAW / "gym_to_gym_drive_times.csv"
    g2g_exists = g2g_path.exists() and g2g_path.stat().st_size > 50
    if g2g_exists:
        print(f"\n✓ Gym-to-gym already pulled — {g2g_path.name} exists. Skipping.")
    else:
        if g2g_path.exists():
            g2g_path.unlink()  # remove empty file from a previous failed run
        print(f"\n[1/2] Pulling gym-to-gym drive times...")
        print(f"  {len(gym_master)} gyms → {len(gym_master)**2 - len(gym_master)} pairs")
        g2g_df = pull_gym_to_gym(gym_master, GOOGLE_API_KEY)
        g2g_df.to_csv(g2g_path, index=False)
        print(f"\n✓ Saved → {g2g_path}  ({len(g2g_df):,} rows)")

        if len(g2g_df) > 0 and "drive_minutes" in g2g_df.columns:
            g2g_df["drive_minutes"] = pd.to_numeric(g2g_df["drive_minutes"], errors="coerce")
            min_times = g2g_df.groupby("origin_gym_id")["drive_minutes"].min()
            print(f"  Nearest same-brand location: avg {min_times.mean():.1f} min drive")

    # ── Gym-to-tracts ─────────────────────────────────────────────────────────
    g2t_path = DATA_RAW / "gym_to_tract_drive_times.csv"
    g2t_exists = g2t_path.exists() and g2t_path.stat().st_size > 50
    if g2t_exists:
        print(f"\n✓ Gym-to-tract already pulled — {g2t_path.name} exists. Skipping.")
    else:
        tract_path = DATA_RAW / "tract_centroids_az.csv"
        if not tract_path.exists():
            print(f"\n✗ Missing tract centroids. Run pull_tract_centroids.py first.")
            sys.exit(1)

        tract_centroids = pd.read_csv(tract_path, dtype={"geoid": str})
        print(f"\n[2/2] Pulling gym-to-tract drive times...")
        print(f"  {len(gym_master)} gyms × ~{len(tract_centroids)} tracts (pre-filtered)")
        print(f"  Estimated cost: ~$35-45  |  Time: ~10 minutes")

        g2t_df = pull_gym_to_tracts(gym_master, tract_centroids, GOOGLE_API_KEY)
        g2t_df.to_csv(g2t_path, index=False)

        in_trade = g2t_df[g2t_df["in_trade_area"] == True]
        print(f"\n✓ Saved → {g2t_path}  ({len(g2t_df):,} rows)")
        print(f"  Trade area tracts per gym (avg): "
              f"{in_trade.groupby('gym_id').size().mean():.1f}")

    print(f"\n{'='*60}")
    print(f"DISTANCE MATRIX PULL COMPLETE")
    print(f"  Commit data/raw/ to GitHub.")


if __name__ == "__main__":
    main()