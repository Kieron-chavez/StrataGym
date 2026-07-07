# =============================================================================
# ml/src/predict.py
#
# Scores a single arbitrary lat/lng — what the frontend calls when a user
# drops a pin. Importable (score_point) and runnable as a CLI:
#
#   python ml/src/predict.py --lat 33.49 --lng -112.05
#
# Feature sourcing order:
#   1. Live computation from raw data (identical code path to score_grid.py)
#   2. Nearest grid cell in data/grid/candidate_grid_features.csv
#   3. Nearest EOS location's row in data/processed/features.csv
#
# opportunity_score = percentile rank of this prediction against the 44
# existing EOS location predictions (82 = better market signals than 82% of
# the current network).
# =============================================================================

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import xgboost as xgb
from common import DataContext, fail, haversine_miles, load_config
from explain import get_score_drivers


@lru_cache(maxsize=1)
def _model() -> xgb.XGBRegressor:
    cfg = load_config()
    if not cfg["paths"]["model"].exists():
        fail(f"{cfg['paths']['model']} not found — run: python ml/src/train.py")
    m = xgb.XGBRegressor()
    m.load_model(str(cfg["paths"]["model"]))
    return m


@lru_cache(maxsize=1)
def _context() -> DataContext | None:
    """Raw-data context for live featurization; None if raw files missing."""
    try:
        return DataContext(load_config())
    except SystemExit:
        return None


@lru_cache(maxsize=1)
def _network() -> pd.DataFrame:
    """The 44 EOS locations with model predictions (for percentile + cannibalization)."""
    cfg = load_config()
    feats_path = cfg["paths"]["features"]
    if not feats_path.exists():
        fail(f"{feats_path} not found — run: python ml/src/features.py")
    df = pd.read_csv(feats_path)
    X = df[cfg["feature_columns"]].values.astype(np.float32)
    df["predicted_checkins"] = _model().predict(X).astype(float)
    return df


@lru_cache(maxsize=1)
def _grid() -> pd.DataFrame | None:
    cfg = load_config()
    path = cfg["paths"]["grid_features"]
    return pd.read_csv(path) if path.exists() else None


def _features_for_point(lat: float, lng: float, cfg: dict) -> dict:
    ctx = _context()
    if ctx is not None:
        return ctx.compute_point_features(lat, lng)

    cols = cfg["feature_columns"]
    grid = _grid()
    if grid is not None:
        d = haversine_miles(lat, lng, grid["latitude"].values, grid["longitude"].values)
        row = grid.iloc[int(np.argmin(d))]
        return {c: float(row[c]) for c in cols}

    net = _network()
    d = haversine_miles(lat, lng, net["latitude"].values, net["longitude"].values)
    row = net.iloc[int(np.argmin(d))]
    feats = {c: float(row[c]) for c in cols}
    feats["years_open"] = float(cfg["synthesis"]["default_years_open"])
    return feats


def _band_label(value: float, bands: list, lower_bound: bool) -> str:
    """bands: [[threshold, label], ...]; lower_bound picks first threshold <= value,
    otherwise first threshold >= value."""
    if lower_bound:
        for threshold, label in bands:  # descending thresholds
            if value >= float(threshold):
                return label
    else:
        for threshold, label in bands:  # ascending thresholds
            if value <= float(threshold):
                return label
    return bands[-1][1]


def score_point(lat: float, lng: float) -> dict:
    cfg = load_config()
    feats = _features_for_point(lat, lng, cfg)

    X = np.array([[feats[c] for c in cfg["feature_columns"]]], dtype=np.float32)
    expected_checkins = float(_model().predict(X)[0])
    expected_checkins = max(expected_checkins, 0.0)

    # Percentile rank vs the 44 existing EOS location predictions
    net = _network()
    network_preds = net["predicted_checkins"].values
    opportunity_score = int(round((expected_checkins > network_preds).mean() * 100))
    score_label = _band_label(opportunity_score, cfg["scoring"]["score_labels"],
                              lower_bound=True)
    percentile_label = (f"Top {max(100 - opportunity_score, 1)}% of candidates"
                        if opportunity_score >= 50
                        else f"Bottom {max(opportunity_score, 1)}% of candidates")

    # Cannibalization: EOS locations within radius, linear distance decay
    radius = float(cfg["scoring"]["cannibalization_radius_mi"])
    max_overlap = float(cfg["scoring"]["cannibalization_max_overlap"])
    dists = haversine_miles(lat, lng, net["latitude"].values, net["longitude"].values)

    nearby = []
    cannibalized_total = 0.0
    for i in np.where(dists <= radius)[0]:
        dist = float(dists[i])
        overlap = max(0.0, 1.0 - dist / radius) * max_overlap
        loc_pred = float(net["predicted_checkins"].iloc[i])
        cannibalized = overlap * loc_pred
        cannibalized_total += cannibalized
        nearby.append({
            "name": str(net["name"].iloc[i]),
            "distance_mi": round(dist, 1),
            "cannibalization_pct": int(round(overlap * 100)),
            "impact": -int(round(cannibalized)),
        })
    nearby.sort(key=lambda g: g["distance_mi"])

    cann_pct = (cannibalized_total / expected_checkins * 100
                if expected_checkins > 0 else 0.0)
    cann_pct = min(cann_pct, 100.0)
    cann_label = _band_label(cann_pct, cfg["scoring"]["cannibalization_labels"],
                             lower_bound=False)
    net_impact = expected_checkins - cannibalized_total

    return {
        "lat": lat,
        "lng": lng,
        "opportunity_score": opportunity_score,
        "score_label": score_label,
        "score_percentile_label": percentile_label,
        "projected_checkins": int(round(expected_checkins)),
        "cannibalization_pct": int(round(cann_pct)),
        "cannibalization_label": cann_label,
        "net_network_impact": int(round(net_impact)),
        "score_drivers": get_score_drivers(feats),
        "nearby_eos_locations": nearby,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score a candidate site")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lng", type=float, required=True)
    args = parser.parse_args()

    result = score_point(args.lat, args.lng)
    print(json.dumps(result, indent=2))
