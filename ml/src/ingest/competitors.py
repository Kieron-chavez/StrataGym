# =============================================================================
# ml/src/ingest/competitors.py
#
# Metro-wide competitor gym sweep via Google Places Text Search.
#
# Unlike ml/scripts/04_pull_competitors_and_pois.py (which searched only around
# each EOS gym and was never run), this sweeps a lattice of search centers
# across the whole Phoenix-metro bounding box so competitor counts are valid
# for ANY point — existing locations, dropped pins, and heatmap grid cells.
#
# API:      https://maps.googleapis.com/maps/api/place/textsearch/json
#           query="gym OR fitness center OR health club", location bias per
#           lattice center, up to 3 pages (60 results) per center.
# Auth:     GOOGLE_API_KEY in StrataGym/.env (Places API enabled).
# Produces: data/raw/competitors_metro.csv with columns:
#           place_id, name, latitude, longitude, rating, is_boutique
#           (is_boutique=1 for studio-style gyms excluded from big-box
#            competitor counts; EOS locations are excluded entirely)
# Cost:     ~$3-6 one-time (Text Search $32/1000 req; covered by Google's
#           monthly free credit). Never overwrites an existing output file.
#
# TODO: for a new metro, update grid.bbox in config.yaml — the sweep lattice
#       derives from it automatically.
# =============================================================================

from __future__ import annotations

import os
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import requests
from common import ML_ROOT, fail, load_config

try:
    from dotenv import load_dotenv
    load_dotenv(ML_ROOT.parent / ".env")
except ImportError:
    pass

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
QUERY = "gym OR fitness center OR health club"


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def search_center(lat: float, lng: float, radius_m: int, key: str) -> list[dict]:
    """One text search with pagination (max 3 pages / 60 results)."""
    results, token = [], None
    for page in range(3):
        params = ({"pagetoken": token, "key": key} if token else
                  {"query": QUERY, "location": f"{lat},{lng}",
                   "radius": radius_m, "key": key})
        try:
            data = requests.get(TEXT_SEARCH_URL, params=params, timeout=15).json()
        except Exception as e:
            print(f"    ✗ request error at ({lat:.2f},{lng:.2f}): {e}")
            return results
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            print(f"    ✗ API status {status} at ({lat:.2f},{lng:.2f})")
            return results
        results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2.1)  # next_page_token needs ~2s to activate
    return results


def main():
    cfg = load_config()
    out_path = cfg["paths"]["competitors"]
    if out_path.exists():
        df = pd.read_csv(out_path)
        print(f"✓ {out_path.name} already exists ({len(df)} competitors) — not overwriting.")
        return

    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        fail("GOOGLE_API_KEY not set in StrataGym/.env (Places API required).")

    bbox = cfg["grid"]["bbox"]
    spacing = cfg["ingest"]["competitor_sweep_spacing_deg"]
    radius_m = cfg["ingest"]["competitor_search_radius_m"]
    boutique_kw = [k.lower() for k in cfg["ingest"]["boutique_keywords"]]

    lats = np.arange(bbox["lat_min"], bbox["lat_max"] + 1e-9, spacing)
    lngs = np.arange(bbox["lng_min"], bbox["lng_max"] + 1e-9, spacing)
    centers = [(la, ln) for la in lats for ln in lngs]
    print(f"Sweeping {len(centers)} search centers "
          f"({len(lats)}×{len(lngs)} lattice, {spacing}° spacing)...")

    places: dict[str, dict] = {}
    for i, (la, ln) in enumerate(centers, 1):
        raw = search_center(la, ln, radius_m, key)
        new = 0
        for r in raw:
            pid = r.get("place_id")
            name = r.get("name", "")
            loc = r.get("geometry", {}).get("location", {})
            if not pid or pid in places or not loc.get("lat"):
                continue
            if "eos fitness" in _norm(name):
                continue  # same brand — handled separately as cannibalization
            places[pid] = {
                "place_id": pid,
                "name": name,
                "latitude": loc["lat"],
                "longitude": loc["lng"],
                "rating": r.get("rating"),
                "is_boutique": int(any(kw in _norm(name) for kw in boutique_kw)),
            }
            new += 1
        print(f"  [{i:3d}/{len(centers)}] ({la:.2f},{ln:.2f}) — "
              f"{len(raw)} results, {new} new  (total {len(places)})")
        time.sleep(0.15)

    if not places:
        fail("Sweep returned zero competitors — check Places API access/quota.")

    df = pd.DataFrame(places.values())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    n_big = int((df["is_boutique"] == 0).sum())
    print(f"\n✓ Saved → {out_path}")
    print(f"  {len(df)} unique competitors ({n_big} big-box, {len(df) - n_big} boutique)")


if __name__ == "__main__":
    main()
