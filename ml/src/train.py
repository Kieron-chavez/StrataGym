# =============================================================================
# ml/src/train.py
#
# Trains the XGBoost check-in model on data/processed/training_data.csv with
# Leave-One-Out cross-validation (44 rows is too small for k-fold).
#
# Outputs:
#   models/model.json    — final model trained on all rows
#   models/metrics.json  — LOO RMSE, LOO R², feature importance ranking
#
# Run from project root:  python ml/src/train.py
# =============================================================================

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import xgboost as xgb
from common import fail, load_config

TARGET = "expected_checkins"


def run_loo_cv(X: np.ndarray, y: np.ndarray, params: dict) -> np.ndarray:
    preds = np.zeros(len(y))
    for i in range(len(y)):
        mask = np.ones(len(y), dtype=bool)
        mask[i] = False
        model = xgb.XGBRegressor(**params)
        model.fit(X[mask], y[mask], verbose=False)
        preds[i] = model.predict(X[~mask])[0]
    return preds


def main():
    cfg = load_config()
    data_path = cfg["paths"]["training_data"]
    if not data_path.exists():
        fail(f"{data_path} not found — run: python ml/src/synthesize.py")

    df = pd.read_csv(data_path)
    feature_cols = cfg["feature_columns"]
    missing = [c for c in feature_cols + [TARGET] if c not in df.columns]
    if missing:
        fail(f"training_data.csv is missing column(s) {missing} — re-run the pipeline")

    X = df[feature_cols].values.astype(np.float32)
    y = df[TARGET].values.astype(np.float32)
    params = cfg["model"]["xgboost"]

    print("=" * 70)
    print(f"train.py — XGBoost, LOO CV on {len(df)} locations, "
          f"{len(feature_cols)} features")
    print("=" * 70)

    print(f"\n[1/3] Leave-One-Out cross-validation ({len(y)} folds)...")
    loo_preds = run_loo_cv(X, y, params)

    rmse = float(np.sqrt(np.mean((y - loo_preds) ** 2)))
    ss_res = float(np.sum((y - loo_preds) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot
    mape = float(np.mean(np.abs((y - loo_preds) / np.maximum(y, 1))) * 100)

    print(f"\n  LOO RMSE: {rmse:,.0f} check-ins/month")
    print(f"  LOO R²:   {r2:.4f}")
    print(f"  LOO MAPE: {mape:.1f}%")

    print(f"\n[2/3] Training final model on all {len(df)} rows...")
    final = xgb.XGBRegressor(**params)
    final.fit(X, y)

    importance = dict(sorted(
        zip(feature_cols, (final.feature_importances_.astype(float))),
        key=lambda kv: kv[1], reverse=True,
    ))

    models_dir = cfg["paths"]["models_dir"]
    models_dir.mkdir(parents=True, exist_ok=True)
    final.save_model(str(cfg["paths"]["model"]))
    metrics = {
        "n_locations": len(df),
        "target": TARGET,
        "cv_strategy": "leave-one-out",
        "loo_rmse": round(rmse, 2),
        "loo_r2": round(r2, 4),
        "loo_mape_pct": round(mape, 2),
        "feature_columns": feature_cols,
        "feature_importance": {k: round(v, 5) for k, v in importance.items()},
        "xgboost_params": params,
    }
    with open(cfg["paths"]["metrics"], "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  ✓ Model   → {cfg['paths']['model']}")
    print(f"  ✓ Metrics → {cfg['paths']['metrics']}")

    print("\n[3/3] Predicted vs synthetic actual (LOO, all rows):")
    warn_pct = float(cfg["model"]["loo_warn_pct"])
    table = pd.DataFrame({
        "name": df["name"],
        "actual": y.astype(int),
        "predicted": loo_preds.round(0).astype(int),
    })
    table["pct_off"] = ((table["predicted"] - table["actual"])
                        / np.maximum(table["actual"], 1) * 100).round(1)
    table["flag"] = np.where(table["pct_off"].abs() > warn_pct, "⚠", "")
    with pd.option_context("display.width", 140, "display.max_rows", None):
        print(table.sort_values("actual", ascending=False).to_string(index=False))

    flagged = table[table["pct_off"].abs() > warn_pct]
    if len(flagged) > 0:
        print(f"\n⚠ WARNING: {len(flagged)} location(s) off by more than {warn_pct:.0f}% — "
              f"that usually flags a data problem (bad trade-area inputs), not a model problem:")
        for _, r in flagged.iterrows():
            print(f"    {r['name']}: actual {r['actual']:,} vs predicted "
                  f"{r['predicted']:,} ({r['pct_off']:+.0f}%)")
    else:
        print(f"\n✓ All locations within ±{warn_pct:.0f}% — no data red flags.")

    print("\nTop feature importances:")
    for k, v in list(importance.items())[:8]:
        print(f"  {k:<28s} {v:.3f}")


if __name__ == "__main__":
    main()
