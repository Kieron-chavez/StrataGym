# =============================================================================
# scripts/08_score_new_location.py
#
# Given a new candidate address (or pre-computed features),
# outputs a site score, revenue projection, and factor breakdown.
#
# This is the core of the product — what EOS actually uses day-to-day.
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import numpy as np
import pandas as pd
import xgboost as xgb

from config.config import *

parser = argparse.ArgumentParser()
parser.add_argument("--version",       default="v1")
parser.add_argument("--features-file", default="model_features.csv")
parser.add_argument("--manifest-file", default="feature_manifest.json")
_args, _ = parser.parse_known_args()

VERSION       = _args.version
FEATURES_FILE = _args.features_file
MANIFEST_FILE = _args.manifest_file

MODELS_VERSION  = MODELS_DIR      / VERSION
REPORTS_VERSION = OUTPUTS_REPORTS / VERSION


def load_model_and_context():
    """Load trained model + training data context for normalization."""
    model = xgb.XGBRegressor()
    model.load_model(str(MODELS_VERSION / "xgb_model.json"))

    features_df = pd.read_csv(DATA_PROCESSED / FEATURES_FILE)

    with open(DATA_PROCESSED / MANIFEST_FILE) as f:
        manifest = json.load(f)

    with open(REPORTS_VERSION / "model_report.json") as f:
        report = json.load(f)

    return model, features_df, manifest, report


def build_candidate_features(candidate: dict, manifest: dict) -> np.ndarray:
    """
    Convert a candidate location dict into the feature vector the model expects.
    Uses numeric_model_features — the exact same columns the model was trained on.
    """
    feature_cols = manifest.get("numeric_model_features", manifest["model_input_features"])
    row = []
    missing = []

    for col in feature_cols:
        if col in candidate:
            val = candidate[col]
            try:
                row.append(float(val))
            except (ValueError, TypeError):
                row.append(0.0)
        else:
            row.append(0.0)
            missing.append(col)

    if missing:
        print(f"  ⚠ Missing features (defaulted to 0): {missing}")

    return np.array(row, dtype=np.float32).reshape(1, -1)


def predict_with_interval(model, X_candidate, training_df, manifest):
    """
    Point prediction + 80% prediction interval using training residuals.
    """
    feature_cols = manifest.get("numeric_model_features", manifest["model_input_features"])
    numeric_feature_cols = [
        c for c in feature_cols
        if c in training_df.columns and pd.api.types.is_numeric_dtype(training_df[c])
    ]
    X_train = training_df[numeric_feature_cols].values.astype(np.float32)

    y_train = training_df[MODEL_TARGET].values
    train_preds = model.predict(X_train)
    residuals = y_train - train_preds
    std_resid = np.std(residuals)

    pred = float(model.predict(X_candidate)[0])
    z = 1.28  # 80% interval
    low  = max(0, pred - z * std_resid)
    high = pred + z * std_resid

    return pred, low, high


def compute_site_score(prediction, training_df):
    """Normalize prediction to 0-100 relative to existing portfolio."""
    y = training_df[MODEL_TARGET].values
    portfolio_min = y.min()
    portfolio_max = y.max()

    score = 100 * (prediction - portfolio_min) / (portfolio_max - portfolio_min + 1e-9)
    return round(float(np.clip(score, 0, 100)), 1)


def compute_revenue_projection(prediction, candidate):
    """
    Project annual revenue from predicted check-ins.
    Uses dues tier from candidate or defaults.
    """
    tier = candidate.get("tier", "Black Card")
    dues = BASE_DUES.get(tier, BASE_DUES["Black Card"])

    # Rough member count: assume avg member checks in 2.5x per week
    # daily_checkins ÷ (check-in frequency per member per day)
    checkins_per_member_per_day = 2.5 / 7
    estimated_members = prediction / checkins_per_member_per_day

    # Retention: assume 75% stay 12 months on average
    avg_months = 12 * 0.75
    annual_revenue = estimated_members * dues * avg_months

    return {
        "estimated_active_members":  round(estimated_members),
        "avg_monthly_dues":          dues,
        "projected_annual_revenue":  round(annual_revenue),
        "projection_note": "Based on 2.5 check-ins/member/week, 75% 12mo retention",
    }


def factor_breakdown(candidate, manifest):
    """
    Explain which factors are helping vs hurting this location.
    Compares candidate values against portfolio percentiles.
    """
    training_df = pd.read_csv(DATA_PROCESSED / "model_features.csv")
    feature_cols = manifest["model_input_features"]

    factors = []
    key_features = {
        "median_household_income":    ("higher is better", True),
        "pct_age_18_34":              ("higher is better", True),
        "competitor_count_3mi":       ("lower is better", False),
        "cannibalization_overlap_pct":("lower is better", False),
        "retail_density_score":       ("higher is better", True),
        "distance_to_freeway_mi":     ("lower is better", False),
        "apartment_density_score":    ("higher is better", True),
    }

    for feat, (direction, higher_better) in key_features.items():
        if feat not in candidate or feat not in training_df.columns:
            continue

        val = candidate[feat]
        col = training_df[feat]
        pct = (col < val).mean() * 100  # percentile vs portfolio

        if higher_better:
            signal = "positive" if pct > 50 else "negative"
        else:
            signal = "positive" if pct < 50 else "negative"

        factors.append({
            "feature":    feat,
            "value":      val,
            "percentile": round(pct, 0),
            "direction":  direction,
            "signal":     signal,
            "label":      f"{feat.replace('_', ' ').title()}: {val} "
                          f"(better than {pct:.0f}% of existing locations)",
        })

    return sorted(factors, key=lambda x: abs(x["percentile"] - 50), reverse=True)


def score_location(candidate: dict, verbose=True):
    """
    Main entry point. Pass a dict of location features, get a full report.
    """
    model, training_df, manifest, report = load_model_and_context()

    X = build_candidate_features(candidate, manifest)
    pred, low, high = predict_with_interval(model, X, training_df, manifest)
    site_score = compute_site_score(pred, training_df)
    revenue    = compute_revenue_projection(pred, candidate)
    factors    = factor_breakdown(candidate, manifest)

    result = {
        "candidate_name":          candidate.get("name", "Unnamed Location"),
        "site_score":              site_score,
        "predicted_daily_checkins": round(pred, 1),
        "prediction_interval_80pct": {
            "low":  round(low, 1),
            "high": round(high, 1),
        },
        "revenue_projection":      revenue,
        "factor_breakdown":        factors,
        "model_info": {
            "trained_on_n_locations": report["n_locations"],
            "cv_mape_pct":            report["metrics"]["mape_pct"],
            "model_r2":               report["metrics"]["r2"],
        }
    }

    if verbose:
        print("\n" + "=" * 55)
        print(f"  SITE ANALYSIS: {result['candidate_name']}")
        print("=" * 55)
        print(f"  Site Score:          {site_score} / 100")
        print(f"  Predicted Check-ins: {pred:.0f}/day  "
              f"(80% CI: {low:.0f}–{high:.0f})")
        print(f"  Est. Active Members: {revenue['estimated_active_members']:,}")
        print(f"  Projected Revenue:   ${revenue['projected_annual_revenue']:,.0f}/yr")
        print(f"\n  Factor Breakdown:")
        for f in factors[:5]:
            icon = "↑" if f["signal"] == "positive" else "↓"
            print(f"    {icon} {f['label']}")
        print(f"\n  Model trained on {report['n_locations']} locations, "
              f"MAPE: {report['metrics']['mape_pct']:.1f}%")

    return result


# ---------------------------------------------------------------------------
# Example usage — run this script directly to test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example candidate location with manually specified features
    # In production: these come from Census API + Google Places calls
    example_candidate = {
        "name":                       "Test Location — Chandler AZ",
        "tier":                       "Black Card",
        "latitude":                   33.3062,
        "longitude":                  -111.8413,
        "monthly_dues_base":          24.99,
        "square_footage":             28_000,
        "median_household_income":    82_000,
        "pct_age_18_34":              0.26,
        "retail_density_score":       0.72,
        "pct_renters":                0.28,
        "population_density":         6_500,
        "school_count_2mi":           4,
        "distance_to_freeway_mi":     0.8,
        "apartment_density_score":    0.21,
        "competitor_count_3mi":       4,
        "competitor_count_5mi":       9,
        "competitor_density_score":   0.38,
        "nearest_competitor_min":     7.2,
        "nearest_brand_location_mi":  3.4,
        "cannibalization_overlap_pct": 0.18,
        "income_per_sqft_market":     2.93,
        "target_demo_density":        1_690,
        "competition_pressure":       0.36,
        "tier_is_black_card":         1,
        "months_since_opening":       0,
        "launch_growth_m1_to_m6":     0,
        "avg_checkins_month1":        0,
    }

    result = score_location(example_candidate, verbose=True)

    REPORTS_VERSION.mkdir(parents=True, exist_ok=True)
    out = REPORTS_VERSION / "example_site_score.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  Full report saved → {out}")