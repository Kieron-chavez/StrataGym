# =============================================================================
# ml/src/score_grid.py
#
# Pre-computes opportunity scores across the Phoenix metro for the heatmap,
# plus per-location scores/tiers/drivers for the 44 EOS pins.
#
# Outputs:
#   data/grid/candidate_grid_features.csv — full feature matrix per grid cell
#   outputs/grid_scores.json              — [{lat, lng, score}] for the heatmap
#   outputs/location_scores.json          — 44 locations with score, tier and
#                                           top SHAP drivers (pin colors +
#                                           Location Profile panel)
#
# Run from project root:  python ml/src/score_grid.py
# =============================================================================

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import xgboost as xgb
from common import DataContext, fail, load_config
from explain import get_score_drivers


def build_grid_features(ctx: DataContext, cfg: dict) -> pd.DataFrame:
    bbox = cfg["grid"]["bbox"]
    spacing = float(cfg["grid"]["spacing_deg"])
    lats = np.arange(bbox["lat_min"], bbox["lat_max"] + 1e-9, spacing)
    lngs = np.arange(bbox["lng_min"], bbox["lng_max"] + 1e-9, spacing)

    print(f"  Grid: {len(lats)} × {len(lngs)} = {len(lats) * len(lngs)} cells "
          f"({spacing}° ≈ 1 mi spacing)")

    rows = []
    for lat in lats:
        for lng in lngs:
            feats = ctx.compute_point_features(float(lat), float(lng))
            rows.append({"latitude": float(lat), "longitude": float(lng), **feats})
    return pd.DataFrame(rows)


def percentile_scores(preds: np.ndarray, network_preds: np.ndarray) -> np.ndarray:
    """Score = % of existing EOS locations this prediction beats (0-100)."""
    return (preds[:, None] > network_preds[None, :]).mean(axis=1) * 100


def main():
    cfg = load_config()
    model_path = cfg["paths"]["model"]
    feats_path = cfg["paths"]["features"]
    if not model_path.exists():
        fail(f"{model_path} not found — run: python ml/src/train.py")
    if not feats_path.exists():
        fail(f"{feats_path} not found — run: python ml/src/features.py")

    cols = cfg["feature_columns"]
    model = xgb.XGBRegressor()
    model.load_model(str(model_path))

    print("=" * 70)
    print("score_grid.py — Phoenix metro opportunity grid")
    print("=" * 70)

    # ── Network predictions (percentile reference) ───────────────────────────
    net = pd.read_csv(feats_path)
    net_X = net[cols].values.astype(np.float32)
    net_preds = model.predict(net_X).astype(float)

    # ── Grid ─────────────────────────────────────────────────────────────────
    print("\n[1/4] Building grid features (KD-tree interpolation from tract data)...")
    ctx = DataContext(cfg)
    grid = build_grid_features(ctx, cfg)
    grid_path = cfg["paths"]["grid_features"]
    grid_path.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(grid_path, index=False)
    print(f"  ✓ Saved → {grid_path}")

    print("\n[2/4] Batch-scoring grid cells...")
    grid_X = grid[cols].values.astype(np.float32)
    grid_preds = np.clip(model.predict(grid_X).astype(float), 0, None)
    scores = percentile_scores(grid_preds, net_preds)

    # Cells with almost nobody reachable in 15 min are not a market — the model
    # would be extrapolating (trees see "0 competitors" and score desert hot).
    # They are excluded from the heatmap output entirely.
    min_pop = float(cfg["grid"]["min_reachable_pop_15min"])
    in_market = grid["reachable_pop_15min"].values >= min_pop
    print(f"  {int((~in_market).sum())} cells below {min_pop:,.0f} reachable pop "
          f"(desert fringe) excluded from heatmap")

    out_dir = cfg["paths"]["outputs_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    grid_scores = [
        {"lat": round(float(r.latitude), 5), "lng": round(float(r.longitude), 5),
         "score": round(float(s), 1)}
        for r, s, ok in zip(grid.itertuples(), scores, in_market) if ok
    ]
    with open(cfg["paths"]["grid_scores"], "w") as f:
        json.dump(grid_scores, f)
    print(f"  ✓ Saved → {cfg['paths']['grid_scores']}  ({len(grid_scores)} cells)")

    # ── Location scores (pins + Location Profile panel) ──────────────────────
    print("\n[3/4] Scoring the 44 EOS locations (score, tier, SHAP drivers)...")
    loc_scores = percentile_scores(net_preds, net_preds)
    q_lo, q_hi = np.quantile(net_preds, cfg["synthesis"]["tier_quantiles"])
    tiers = np.select([net_preds >= q_hi, net_preds <= q_lo],
                      ["top", "under"], default="average")

    locations = []
    for i, row in net.iterrows():
        locations.append({
            "gym_id": row["gym_id"],
            "name": row["name"],
            "lat": float(row["latitude"]),
            "lng": float(row["longitude"]),
            "predicted_checkins": int(round(float(net_preds[i]))),
            "score": round(float(loc_scores[i]), 1),
            "tier": str(tiers[i]),
            "score_drivers": get_score_drivers(row[cols]),
        })
    with open(cfg["paths"]["location_scores"], "w") as f:
        json.dump(locations, f, indent=2)
    print(f"  ✓ Saved → {cfg['paths']['location_scores']}")

    # ── Sanity summary (in-market cells only) ────────────────────────────────
    print("\n[4/4] Sanity summary")
    hot_t = float(cfg["grid"]["heatmap_thresholds"]["hot"])
    warm_t = float(cfg["grid"]["heatmap_thresholds"]["warm"])
    m_scores = scores[in_market]
    hot = m_scores > hot_t
    warm = (m_scores >= warm_t) & (m_scores <= hot_t)
    cold = m_scores < warm_t
    print(f"  Score distribution (in-market): min {m_scores.min():.0f} | "
          f"median {np.median(m_scores):.0f} | max {m_scores.max():.0f}")
    print(f"  Hot  (>{hot_t:.0f}):  {hot.sum():4d} cells")
    print(f"  Warm ({warm_t:.0f}–{hot_t:.0f}): {warm.sum():4d} cells")
    print(f"  Cold (<{warm_t:.0f}):  {cold.sum():4d} cells")

    # Any remaining hot cells with thin population = extrapolation red flag
    suspicious = (scores > hot_t) & in_market & \
        (grid["reachable_pop_15min"].values < 2 * min_pop)
    if suspicious.sum() > 0:
        sus = grid[suspicious]
        print(f"\n  ⚠ {suspicious.sum()} hot cell(s) have <{2 * min_pop:,.0f} people within "
              f"15 min — verify these aren't desert fringe / outside metro:")
        with pd.option_context("display.max_rows", 10):
            print(sus[["latitude", "longitude", "reachable_pop_15min"]]
                  .head(10).to_string(index=False))
    else:
        print("\n  ✓ No hot zones in low-population areas.")

    print(f"\n  Location tiers: "
          f"{pd.Series(tiers).value_counts().to_dict()}")


if __name__ == "__main__":
    main()
