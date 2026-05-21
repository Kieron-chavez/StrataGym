# =============================================================================
# scripts/06_build_feature_matrix.py
#
# Joins all pulled data sources into a single model-ready feature matrix.
# Inputs (all from data/raw/):
#   - eos_locations.csv              (from 01_pull_eos_locations.py)
#   - census_tracts_combined.csv     (from 02_pull_census_demographics.py)
#   - tract_centroids_az.csv         (from 03_pull_tract_centroids.py)
#   - competitors_per_gym.csv        (from 04_pull_competitors_and_pois.py)
#   - pois_per_gym.csv               (from 04_pull_competitors_and_pois.py)
#   - gym_to_tract_drive_times.csv   (from 05_pull_drive_times.py)
#   - gym_to_gym_drive_times.csv     (from 05_pull_drive_times.py)
#
# Output: data/processed/model_features.csv
#
# HOW TO USE:
#   1. Run scripts 01–05 once to populate data/raw/
#   2. Run this script
#   3. Run 07_train_model.py
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import json
from config.config import *


def check_required_files():
    """Fail fast if any raw data files are missing."""
    required = [
        DATA_RAW / "census_tracts_combined.csv",
        DATA_RAW / "tract_centroids_az.csv",
        DATA_RAW / "gym_to_tract_drive_times.csv",
        DATA_RAW / "gym_to_gym_drive_times.csv",
        DATA_RAW / "competitors_per_gym.csv",
        DATA_RAW / "pois_per_gym.csv",
    ]
    missing = [f for f in required if not f.exists()]
    if missing:
        print("\n✗ Missing required files. Run these scripts first:")
        for f in missing:
            script_map = {
                "census_tracts_combined.csv":   "02_pull_census_demographics.py",
                "tract_centroids_az.csv":       "03_pull_tract_centroids.py",
                "gym_to_tract_drive_times.csv": "05_pull_drive_times.py",
                "gym_to_gym_drive_times.csv":   "05_pull_drive_times.py",
                "competitors_per_gym.csv":      "04_pull_competitors_and_pois.py",
                "pois_per_gym.csv":             "04_pull_competitors_and_pois.py",
            }
            script = script_map.get(f.name, "unknown script")
            print(f"   python scripts/{script}   →  creates {f.name}")
        sys.exit(1)
    print("✓ All required raw data files found")


def load_all():
    census      = pd.read_csv(DATA_RAW / "census_tracts_combined.csv",
                               dtype={"geoid": str})
    centroids   = pd.read_csv(DATA_RAW / "tract_centroids_az.csv",
                               dtype={"geoid": str})
    g2t         = pd.read_csv(DATA_RAW / "gym_to_tract_drive_times.csv",
                               dtype={"tract_geoid": str})
    g2g         = pd.read_csv(DATA_RAW / "gym_to_gym_drive_times.csv")
    competitors = pd.read_csv(DATA_RAW / "competitors_per_gym.csv")
    pois        = pd.read_csv(DATA_RAW / "pois_per_gym.csv")
    gym_master  = pd.read_csv(DATA_RAW / "eos_locations.csv",
                               parse_dates=["grand_opening_date"])
    checkins    = pd.read_csv(DATA_RAW / "checkin_history.csv",
                               parse_dates=["date"])

    print(f"  Census tracts:   {len(census):,}")
    print(f"  Tract centroids: {len(centroids):,}")
    print(f"  Gym-to-tract:    {len(g2t):,} rows")
    print(f"  Gym-to-gym:      {len(g2g):,} rows")
    print(f"  Competitor data: {len(competitors)} gyms")
    print(f"  POI data:        {len(pois)} gyms")
    print(f"  Gym master:      {len(gym_master)} gyms")
    print(f"  Check-in rows:   {len(checkins):,}")

    return census, centroids, g2t, g2g, competitors, pois, gym_master, checkins


def compute_trade_area_demographics(gym_master, g2t, census):
    """
    For each gym, compute weighted-average demographics across all census
    tracts within the 15-minute drive-time trade area.
    Weights = tract population (bigger tracts count more).
    """
    # Join tract demographics to drive-time table
    g2t_demo = g2t[g2t["in_trade_area"] == True].merge(
        census[["geoid", "total_population", "median_household_income",
                "pct_age_18_34", "pct_renters", "pct_college_plus",
                "median_age"]],
        left_on="tract_geoid",
        right_on="geoid",
        how="left"
    )

    trade_area_rows = []

    for gym_id in gym_master["gym_id"]:
        tracts = g2t_demo[g2t_demo["gym_id"] == gym_id].copy()

        if len(tracts) == 0:
            # No trade area data — fall back to gym's own location defaults
            trade_area_rows.append({"gym_id": gym_id,
                                    "trade_area_tract_count": 0})
            continue

        # Population-weighted average
        pop = tracts["total_population"].fillna(0)
        total_pop = pop.sum()

        if total_pop == 0:
            weights = np.ones(len(tracts)) / len(tracts)
        else:
            weights = pop / total_pop

        def wavg(col):
            vals = tracts[col].fillna(tracts[col].median())
            return round(float((vals * weights).sum()), 4)

        trade_area_rows.append({
            "gym_id":                        gym_id,
            "trade_area_total_population":   int(total_pop),
            "trade_area_tract_count":        len(tracts),
            "trade_area_median_income":      round(wavg("median_household_income"), 0),
            "trade_area_pct_age_18_34":      wavg("pct_age_18_34"),
            "trade_area_pct_renters":        wavg("pct_renters"),
            "trade_area_pct_college_plus":   wavg("pct_college_plus"),
            "trade_area_median_age":         wavg("median_age"),
        })

    return pd.DataFrame(trade_area_rows)


def compute_cannibalization(gym_master, g2g):
    """
    For each gym, find nearest same-brand location and estimate trade area overlap.
    Uses real drive times from Distance Matrix pull.
    """
    g2g["drive_minutes"] = pd.to_numeric(g2g["drive_minutes"], errors="coerce")

    cannibal_rows = []

    for gym_id in gym_master["gym_id"]:
        outbound = g2g[g2g["origin_gym_id"] == gym_id].copy()
        outbound = outbound.dropna(subset=["drive_minutes"])

        if len(outbound) == 0:
            cannibal_rows.append({
                "gym_id": gym_id,
                "nearest_brand_gym_id":       None,
                "nearest_brand_drive_minutes": None,
                "nearest_brand_distance_miles": None,
                "cannibalization_overlap_pct":  0.0,
            })
            continue

        nearest = outbound.loc[outbound["drive_minutes"].idxmin()]

        # Overlap estimate: full at <5 min, zero at >25 min, linear between
        drive_min = nearest["drive_minutes"]
        overlap = float(np.clip(1 - (drive_min - 5) / 20, 0, 1))

        cannibal_rows.append({
            "gym_id":                       gym_id,
            "nearest_brand_gym_id":         nearest["dest_gym_id"],
            "nearest_brand_drive_minutes":  round(drive_min, 2),
            "nearest_brand_distance_miles": nearest.get("distance_miles"),
            "cannibalization_overlap_pct":  round(overlap, 4),
        })

    return pd.DataFrame(cannibal_rows)


def compute_target_variable(gym_master, checkins):
    """Same target computation as 02_feature_engineering.py."""
    targets = []
    for _, gym in gym_master.iterrows():
        gid       = gym["gym_id"]
        open_date = gym["grand_opening_date"]
        window_start = open_date + pd.Timedelta(days=300)
        window_end   = open_date + pd.Timedelta(days=420)

        mask = (
            (checkins["gym_id"] == gid) &
            (checkins["date"] >= window_start) &
            (checkins["date"] <= window_end) &
            (checkins["gym_was_open"] == True)
        )
        window_data = checkins[mask]

        if len(window_data) < 14:
            avg = checkins[
                (checkins["gym_id"] == gid) &
                (checkins["gym_was_open"] == True)
            ]["checkin_count"].mean()
        else:
            avg = window_data["checkin_count"].mean()

        targets.append({"gym_id": gid, MODEL_TARGET: round(avg, 2)})

    return pd.DataFrame(targets)


def build_final_features(gym_master, trade_area, cannibal,
                         competitors, pois, targets):
    """Join all real features into the final model matrix."""

    df = gym_master[[
        "gym_id", "gym_name", "cluster", "latitude", "longitude",
        "grand_opening_date", "square_footage", "tier", "monthly_dues_base",
        "status",
    ]].copy()

    df = df.merge(trade_area,  on="gym_id", how="left")
    df = df.merge(cannibal,    on="gym_id", how="left")
    df = df.merge(competitors[["gym_id", "competitor_count_3mi",
                                "competitor_count_5mi", "boutique_count_3mi",
                                "total_fitness_count_3mi"]],
                  on="gym_id", how="left")
    df = df.merge(pois[["gym_id", "grocery_count_1mi", "restaurant_count_1mi",
                         "school_count_2mi", "apartment_count_2mi",
                         "retail_density_score"]],
                  on="gym_id", how="left")
    df = df.merge(targets, on="gym_id", how="left")

    # Derived features
    df["tier_is_black_card"] = (df["tier"] == "Black Card").astype(int)

    df["target_demo_density"] = (
        df["trade_area_pct_age_18_34"].fillna(0) *
        df["trade_area_total_population"].fillna(0)
    ).round(0)

    df["income_per_sqft_market"] = (
        df["trade_area_median_income"].fillna(0) /
        df["square_footage"].replace(0, pd.NA)
    ).round(4)

    df["months_since_opening"] = (
        (pd.Timestamp.today() - df["grand_opening_date"]).dt.days / 30.44
    ).round(1)

    # Competition pressure score
    df["competitor_density_score"] = (
        df["competitor_count_3mi"].fillna(0) * 0.6 +
        df["boutique_count_3mi"].fillna(0) * 0.2
    ).round(4)

    df["competition_pressure"] = (
        df["competitor_density_score"] *
        (1 - df["cannibalization_overlap_pct"].fillna(0) * 0.5)
    ).round(4)

    return df


def main():
    print("=" * 60)
    print("Feature Engineering v2 — Real API Data")
    print("=" * 60)

    print("\n[1/7] Checking required files...")
    check_required_files()

    print("\n[2/7] Loading all data sources...")
    census, centroids, g2t, g2g, competitors, pois, gym_master, checkins = load_all()

    print("\n[3/7] Computing trade area demographics (real Census data)...")
    trade_area = compute_trade_area_demographics(gym_master, g2t, census)
    print(f"  Avg tracts in trade area: {trade_area['trade_area_tract_count'].mean():.1f}")
    print(f"  Avg trade area income:    ${trade_area['trade_area_median_income'].mean():,.0f}")

    print("\n[4/7] Computing cannibalization from real drive times...")
    cannibal = compute_cannibalization(gym_master, g2g)
    print(f"  Avg nearest brand location: {cannibal['nearest_brand_drive_minutes'].mean():.1f} min")

    print("\n[5/7] Computing target variable...")
    targets = compute_target_variable(gym_master, checkins)
    print(f"  Target range: {targets[MODEL_TARGET].min():.0f} – {targets[MODEL_TARGET].max():.0f}")

    print("\n[6/7] Building final feature matrix...")
    df = build_final_features(gym_master, trade_area, cannibal,
                              competitors, pois, targets)
    print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")

    # Null check
    null_cols = df.isnull().sum()
    null_cols = null_cols[null_cols > 0]
    if len(null_cols) > 0:
        print(f"\n  ⚠ Columns with nulls:")
        print(null_cols.to_string())

    print("\n[7/7] Saving...")
    out_path = DATA_PROCESSED / "model_features_real.csv"
    df.to_csv(out_path, index=False)
    print(f"  ✓ Saved → {out_path}")

    # Update manifest
    exclude = ["gym_id", "gym_name", "cluster", "grand_opening_date",
               "tier", "status", "nearest_brand_gym_id", MODEL_TARGET]
    numeric_features = [
        c for c in df.columns
        if c not in exclude and pd.api.types.is_numeric_dtype(df[c])
    ]

    manifest = {
        "model_input_features":   numeric_features,
        "numeric_model_features": numeric_features,
        "target":                 MODEL_TARGET,
        "data_source":            "real_api",
        "n_samples":              len(df),
    }
    manifest_path = DATA_PROCESSED / "feature_manifest_real.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  ✓ Manifest saved → {manifest_path}")

    print(f"\n  Features ({len(numeric_features)}):")
    for f in numeric_features:
        print(f"    - {f}")

    print(f"\n{'='*60}")
    print(f"  Next: run 07_train_model.py:")
    print(f"        DATA_PROCESSED / 'model_features_real.csv'")
    print(f"        DATA_PROCESSED / 'feature_manifest_real.json'")


if __name__ == "__main__":
    main()