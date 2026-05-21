# =============================================================================
# scripts/pull_tract_centroids.py
#
# Downloads Census Gazetteer file and extracts lat/lon centroid for every
# census tract in Maricopa + Pinal counties, Arizona.
#
# PULL ONCE — saves to:
#   data/raw/tract_centroids_az.csv
#
# COMMIT to GitHub. No API key needed — this is a free file download.
#
# Cost: FREE
# Time: ~20 seconds (downloads ~7MB zip, filters to AZ)
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import pandas as pd
import zipfile
import io
from config.config import *


GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2023_Gazetteer/2023_Gaz_tracts_national.zip"
)


def main():
    print("=" * 60)
    print("Census Gazetteer — Tract Centroids (AZ)")
    print("=" * 60)

    out_path = DATA_RAW / "tract_centroids_az.csv"

    if out_path.exists():
        print(f"\n✓ Already downloaded — {out_path} exists.")
        df = pd.read_csv(out_path)
        print(f"  {len(df)} AZ tracts loaded.")
        return df

    print("\n  Downloading national gazetteer (~7MB)...")
    resp = requests.get(GAZETTEER_URL, timeout=60)
    resp.raise_for_status()

    print("  Extracting and filtering to Arizona...")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        filename = [f for f in z.namelist() if f.endswith(".txt")][0]
        with z.open(filename) as f:
            df = pd.read_csv(f, sep="\t", dtype={"GEOID": str})

    # Standardize column names (different vintages use different cases)
    df.columns = [c.strip().upper() for c in df.columns]

    # Filter to Arizona (FIPS starts with 04)
    # Maricopa = 04013, Pinal = 04021
    az_prefixes = [f"04{c}" for c in COUNTIES]  # ["04013", "04021"]
    mask = df["GEOID"].str.startswith(tuple(az_prefixes))
    az_df = df[mask].copy()

    # Keep only what we need
    keep_cols = {
        "GEOID":    "geoid",
        "INTPTLAT": "centroid_lat",
        "INTPTLONG": "centroid_lon",
        "ALAND_SQMI": "land_area_sqmi",
    }
    az_df = az_df[[c for c in keep_cols if c in az_df.columns]].rename(columns=keep_cols)

    # Clean up
    az_df["centroid_lat"] = pd.to_numeric(az_df["centroid_lat"], errors="coerce")
    az_df["centroid_lon"] = pd.to_numeric(az_df["centroid_lon"], errors="coerce")
    az_df = az_df.dropna(subset=["centroid_lat", "centroid_lon"])

    # Derive population density placeholder (will be joined from Census data)
    az_df = az_df.reset_index(drop=True)

    az_df.to_csv(out_path, index=False)
    print(f"\n✓ Saved → {out_path}")
    print(f"  {len(az_df)} AZ tracts with centroids")
    print(f"  Lat range:  {az_df['centroid_lat'].min():.4f} – {az_df['centroid_lat'].max():.4f}")
    print(f"  Lon range:  {az_df['centroid_lon'].min():.4f} – {az_df['centroid_lon'].max():.4f}")

    return az_df


if __name__ == "__main__":
    main()