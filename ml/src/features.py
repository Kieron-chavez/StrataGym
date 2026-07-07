# =============================================================================
# ml/src/features.py
#
# Merges all raw data sources into one clean feature matrix — one row per EOS
# location — and writes data/processed/features.csv.
#
# Inputs (data/raw/):
#   eos_locations.csv, census_tracts_combined.csv (+ census_age_35_44.csv),
#   tract_centroids_az.csv, competitors_metro.csv
# Output:
#   data/processed/features.csv
#
# Missing files or columns fail loudly with instructions — nothing is silently
# zero-filled.
#
# Run from project root:  python ml/src/features.py
# =============================================================================

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from common import DataContext, compute_years_open, load_config


def build_features() -> pd.DataFrame:
    cfg = load_config()
    ctx = DataContext(cfg)

    years = compute_years_open(ctx.eos, cfg["synthesis"]["default_years_open"])
    names = ctx.eos_display_names()

    rows = []
    for i, gym in ctx.eos.iterrows():
        feats = ctx.compute_point_features(
            gym["latitude"], gym["longitude"],
            years_open=float(years.iloc[i]),
            exclude_self_eos=True,
        )
        rows.append({
            "gym_id": gym["gym_id"],
            "name": names[i],
            "latitude": gym["latitude"],
            "longitude": gym["longitude"],
            **feats,
        })

    df = pd.DataFrame(rows)

    # Guarantee the exact training column set from config exists
    missing = [c for c in cfg["feature_columns"] if c not in df.columns]
    if missing:
        raise RuntimeError(f"Internal error — feature columns not produced: {missing}")

    # Sanity: no location should have an empty trade area
    empty = df[df["total_population"] <= 0]
    if len(empty) > 0:
        print(f"\n⚠ WARNING: {len(empty)} location(s) have zero trade-area population "
              f"(outside tract coverage?):")
        print(empty[["gym_id", "name", "latitude", "longitude"]].to_string(index=False))

    return df


def main():
    cfg = load_config()
    out_path = cfg["paths"]["features"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("features.py — building feature matrix for EOS locations")
    print("=" * 70)

    df = build_features()
    df.to_csv(out_path, index=False)

    print(f"\n✓ Saved → {out_path}  ({len(df)} locations × {len(df.columns)} columns)")
    print("\nSummary statistics:")
    with pd.option_context("display.width", 160, "display.max_columns", None,
                           "display.float_format", "{:,.1f}".format):
        print(df[cfg["feature_columns"]].describe().loc[["mean", "min", "max"]].T)


if __name__ == "__main__":
    main()
