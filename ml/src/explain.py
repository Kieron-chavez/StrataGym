# =============================================================================
# ml/src/explain.py
#
# SHAP-based score drivers for any prediction.
#
# get_score_drivers(feature_row) → top-N features by |SHAP|, each as
#   {"label": "Competitor density", "points": 18, "direction": "positive"}
# with contributions scaled to a -30..+30 point range for the UI.
#
# Uses shap.TreeExplainer (fast + exact for XGBoost) when the shap package is
# installed; otherwise falls back to XGBoost's native pred_contribs, which is
# the same exact TreeSHAP algorithm — so the API server doesn't need the heavy
# shap/numba dependency.
#
# Also runnable standalone to sanity-check drivers for one training row:
#   python ml/src/explain.py [--row 0]
# =============================================================================

from __future__ import annotations

import argparse
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import xgboost as xgb
from common import fail, load_config

try:
    import shap  # noqa: F401
    _HAS_SHAP = True
except ImportError:
    _HAS_SHAP = False


@lru_cache(maxsize=1)
def _load_model() -> xgb.XGBRegressor:
    cfg = load_config()
    model_path = cfg["paths"]["model"]
    if not model_path.exists():
        fail(f"{model_path} not found — run: python ml/src/train.py")
    model = xgb.XGBRegressor()
    model.load_model(str(model_path))
    return model


@lru_cache(maxsize=1)
def _explainer():
    return shap.TreeExplainer(_load_model()) if _HAS_SHAP else None


def _shap_values(X: np.ndarray) -> np.ndarray:
    """Exact TreeSHAP contributions, shape (n, n_features)."""
    if _HAS_SHAP:
        return np.asarray(_explainer().shap_values(X))
    booster = _load_model().get_booster()
    contribs = booster.predict(xgb.DMatrix(X), pred_contribs=True)
    return contribs[:, :-1]  # last column is the bias term


def get_score_drivers(feature_row, top_n: int | None = None) -> list[dict]:
    """
    feature_row: dict, pandas Series, or 1-D array ordered per
    config feature_columns. Returns the top features by |SHAP|, scaled to
    a ±points_scale range so they read as "+18 pts" in the UI.
    """
    cfg = load_config()
    cols = cfg["feature_columns"]
    labels = cfg["explain"]["labels"]
    scale = float(cfg["explain"]["points_scale"])
    top_n = top_n or int(cfg["explain"]["top_n_drivers"])

    if isinstance(feature_row, dict):
        missing = [c for c in cols if c not in feature_row]
        if missing:
            fail(f"get_score_drivers: feature_row missing {missing}")
        x = np.array([[float(feature_row[c]) for c in cols]], dtype=np.float32)
    elif isinstance(feature_row, pd.Series):
        x = feature_row[cols].values.astype(np.float32).reshape(1, -1)
    else:
        x = np.asarray(feature_row, dtype=np.float32).reshape(1, -1)

    sv = _shap_values(x)[0]

    # Scale so the single largest |contribution| maps to points_scale
    max_abs = float(np.max(np.abs(sv))) or 1.0
    points = sv / max_abs * scale

    order = np.argsort(-np.abs(sv))[:top_n]
    return [
        {
            "label": labels.get(cols[i], cols[i].replace("_", " ").capitalize()),
            "points": int(round(points[i])),
            "direction": "positive" if sv[i] >= 0 else "negative",
        }
        for i in order
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--row", type=int, default=0,
                        help="training_data.csv row index to explain")
    args = parser.parse_args()

    cfg = load_config()
    df = pd.read_csv(cfg["paths"]["training_data"])
    row = df.iloc[args.row]
    print(f"Score drivers for: {row['name']}  "
          f"(expected_checkins={row['expected_checkins']:,.0f})")
    print(f"(engine: {'shap.TreeExplainer' if _HAS_SHAP else 'xgboost pred_contribs'})")
    for d in get_score_drivers(row):
        sign = "+" if d["direction"] == "positive" else "−"
        print(f"  {sign}{abs(d['points']):>2d} pts  {d['label']}")
