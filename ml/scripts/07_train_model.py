# =============================================================================
# scripts/07_train_model.py
#
# Trains XGBoost model using Leave-One-Out cross-validation.
# Outputs:
#   models/xgb_model.json          — trained model
#   outputs/charts/backtest.png    — predicted vs actual scatter
#   outputs/charts/feat_importance.png
#   outputs/reports/model_report.json
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import warnings
warnings.filterwarnings("ignore")

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
CHARTS_VERSION  = OUTPUTS_CHARTS  / VERSION
REPORTS_VERSION = OUTPUTS_REPORTS / VERSION


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_features():
    path = DATA_PROCESSED / FEATURES_FILE
    if not path.exists():
        raise FileNotFoundError(f"Run feature engineering first.\nExpected: {path}")

    df = pd.read_csv(path, parse_dates=["grand_opening_date"])

    with open(DATA_PROCESSED / MANIFEST_FILE) as f:
        manifest = json.load(f)

    return df, manifest


# ---------------------------------------------------------------------------
# Prepare X, y
# ---------------------------------------------------------------------------

def prepare_matrices(df, feature_cols):
    """Return X (features), y (target), and feature names."""
    # Exclude non-numeric and ID columns
    exclude = ["gym_id", "gym_name", "cluster", "grand_opening_date",
               "tier", "status", "_true_performance_score",
               "_mature_daily_checkins", MODEL_TARGET,
               "window_days_available"]

    numeric_features = [
        c for c in feature_cols
        if c not in exclude and df[c].dtype in [np.float64, np.int64, float, int]
    ]

    X = df[numeric_features].values.astype(np.float32)
    y = df[MODEL_TARGET].values.astype(np.float32)

    return X, y, numeric_features

# ---------------------------------------------------------------------------
# LOO Cross-Validation
# ---------------------------------------------------------------------------

def run_loo_cv(X, y, feature_names, df):
    """
    Leave-One-Out CV: train on 41, predict held-out gym, repeat 42x.
    Returns per-gym predictions and full error summary.
    """
    loo = LeaveOneOut()
    predictions = np.zeros(len(y))
    prediction_lows  = np.zeros(len(y))
    prediction_highs = np.zeros(len(y))

    print(f"  Running LOO CV ({len(y)} folds)...")

    for fold, (train_idx, test_idx) in enumerate(loo.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train         = y[train_idx]

        model = xgb.XGBRegressor(**XGBOOST_PARAMS)
        model.fit(X_train, y_train, verbose=False)

        pred = model.predict(X_test)[0]
        predictions[test_idx[0]] = pred

        # Prediction interval via residual bootstrap on training set
        train_preds = model.predict(X_train)
        residuals   = y_train - train_preds
        std_resid   = np.std(residuals)
        z = 1.28  # 80% interval
        prediction_lows[test_idx[0]]  = pred - z * std_resid
        prediction_highs[test_idx[0]] = pred + z * std_resid

        if (fold + 1) % 10 == 0:
            print(f"    Fold {fold+1}/{len(y)} complete")

    return predictions, prediction_lows, prediction_highs


# ---------------------------------------------------------------------------
# Final model (trained on all data for deployment)
# ---------------------------------------------------------------------------

def train_final_model(X, y, feature_names):
    """Train on full dataset. This is the model used for new site scoring."""
    model = xgb.XGBRegressor(**XGBOOST_PARAMS)
    model.fit(X, y)

    importance = dict(zip(feature_names, model.feature_importances_))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    return model, importance


# ---------------------------------------------------------------------------
# Compute site score (0-100)
# ---------------------------------------------------------------------------

def compute_site_scores(predictions, y):
    """Normalize predictions to 0-100 site score for reporting."""
    all_vals   = np.concatenate([predictions, y])
    min_val    = all_vals.min()
    max_val    = all_vals.max()
    pred_score = 100 * (predictions - min_val) / (max_val - min_val + 1e-9)
    true_score = 100 * (y - min_val)           / (max_val - min_val + 1e-9)
    return pred_score.round(1), true_score.round(1)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

STYLE = {
    "bg":       "#080C14",
    "panel":    "#0D1420",
    "border":   "#1A2332",
    "accent":   "#00E5B4",
    "blue":     "#4D9FFF",
    "red":      "#FF6B6B",
    "yellow":   "#FFB800",
    "text":     "#E8EDF5",
    "muted":    "#4A6080",
}


def plot_backtest(df, predictions, pred_lows, pred_highs, mae, r2, mape):
    """Predicted vs actual scatter — the demo chart."""
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor(STYLE["bg"])
    ax.set_facecolor(STYLE["panel"])

    y_true = df[MODEL_TARGET].values

    # Prediction interval lines
    for i in range(len(y_true)):
        ax.plot(
            [y_true[i], y_true[i]],
            [pred_lows[i], pred_highs[i]],
            color=STYLE["accent"], alpha=0.15, linewidth=1.5, zorder=1
        )

    # Scatter points colored by cluster
    clusters = df["cluster"].unique()
    cluster_colors = {
        c: plt.cm.Set2(i / len(clusters))
        for i, c in enumerate(clusters)
    }

    for cluster in clusters:
        mask = df["cluster"] == cluster
        ax.scatter(
            y_true[mask], predictions[mask],
            c=[cluster_colors[cluster]],
            s=90, alpha=0.85, zorder=3,
            edgecolors=STYLE["bg"], linewidths=0.8,
            label=cluster,
        )

    # Gym labels for outliers
    residuals = np.abs(predictions - y_true)
    threshold = np.percentile(residuals, 75)
    for i, row in df.iterrows():
        if residuals[df.index.get_loc(i)] > threshold:
            ax.annotate(
                row["gym_id"],
                (y_true[df.index.get_loc(i)], predictions[df.index.get_loc(i)]),
                fontsize=7, color=STYLE["muted"], alpha=0.7,
                xytext=(5, 5), textcoords="offset points"
            )

    # Perfect prediction line
    all_vals = np.concatenate([y_true, predictions])
    lim = (all_vals.min() * 0.9, all_vals.max() * 1.1)
    ax.plot(lim, lim, "--", color=STYLE["muted"], alpha=0.5,
            linewidth=1, label="Perfect prediction", zorder=2)

    # ±20% bands
    x_line = np.array(lim)
    ax.fill_between(x_line, x_line * 0.8, x_line * 1.2,
                    color=STYLE["accent"], alpha=0.05, zorder=1)

    # Metrics box
    metrics_text = f"MAE: {mae:.0f} check-ins/day\nMAPE: {mape:.1f}%\nR²: {r2:.3f}"
    ax.text(0.03, 0.97, metrics_text,
            transform=ax.transAxes, fontsize=10,
            verticalalignment="top",
            color=STYLE["text"],
            bbox=dict(boxstyle="round,pad=0.5", facecolor=STYLE["bg"],
                      edgecolor=STYLE["accent"], alpha=0.9))

    # V1 pass/fail
    v1_pass = mape <= (V1_SUCCESS_MAE_PCT * 100)
    status_color = STYLE["accent"] if v1_pass else STYLE["red"]
    status_text  = "V1 PASS ✓" if v1_pass else "V1 NOT YET ✗"
    ax.text(0.97, 0.03, status_text,
            transform=ax.transAxes, fontsize=11, fontweight="bold",
            ha="right", va="bottom", color=status_color)

    ax.set_xlabel("Actual Daily Check-ins (12mo Maturity)", color=STYLE["text"], fontsize=11)
    ax.set_ylabel("Predicted Daily Check-ins", color=STYLE["text"], fontsize=11)
    ax.set_title("Back-Test: Predicted vs Actual Performance\n(Leave-One-Out Cross-Validation)",
                 color=STYLE["text"], fontsize=13, pad=15)

    ax.tick_params(colors=STYLE["muted"])
    for spine in ax.spines.values():
        spine.set_edgecolor(STYLE["border"])
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.grid(True, color=STYLE["border"], alpha=0.5, linewidth=0.5)

    legend = ax.legend(loc="upper left", fontsize=8,
                       facecolor=STYLE["panel"], edgecolor=STYLE["border"],
                       labelcolor=STYLE["text"])

    CHARTS_VERSION.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    out = CHARTS_VERSION / "backtest.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=STYLE["bg"])
    plt.close()
    print(f"  Saved → {out}")


def plot_feature_importance(importance, top_n=15):
    """Feature importance bar chart — shows which factors drive performance."""
    items = list(importance.items())[:top_n]
    names = [i[0].replace("_", " ").title() for i in items]
    vals  = [i[1] for i in items]

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(STYLE["bg"])
    ax.set_facecolor(STYLE["panel"])

    # Color by expected signal — known drivers get accent color
    known_drivers = {
        "median household income", "pct age 18 34",
        "target demo density", "competition pressure",
        "cannibalization overlap pct",
    }
    colors = [
        STYLE["accent"] if n.lower() in known_drivers else STYLE["blue"]
        for n in names
    ]

    bars = ax.barh(range(len(names)), vals, color=colors,
                   edgecolor=STYLE["bg"], linewidth=0.5)

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, color=STYLE["text"], fontsize=10)
    ax.set_xlabel("Feature Importance (XGBoost gain)", color=STYLE["text"])
    ax.set_title("What Drives Gym Performance\n(Feature Importance — Final Model)",
                 color=STYLE["text"], fontsize=13, pad=15)

    ax.tick_params(colors=STYLE["muted"])
    for spine in ax.spines.values():
        spine.set_edgecolor(STYLE["border"])
    ax.grid(True, axis="x", color=STYLE["border"], alpha=0.5, linewidth=0.5)

    legend_patches = [
        mpatches.Patch(color=STYLE["accent"], label="Known signal feature"),
        mpatches.Patch(color=STYLE["blue"],   label="Discovered feature"),
    ]
    ax.legend(handles=legend_patches, loc="lower right",
              facecolor=STYLE["panel"], edgecolor=STYLE["border"],
              labelcolor=STYLE["text"])

    plt.tight_layout()
    out = CHARTS_VERSION / "feature_importance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=STYLE["bg"])
    plt.close()
    print(f"  Saved → {out}")


def plot_score_ranking(df, pred_scores, true_scores):
    """Rank all gyms by predicted score — the actionable output."""
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(STYLE["bg"])
    ax.set_facecolor(STYLE["panel"])

    sorted_idx = np.argsort(pred_scores)[::-1]
    gym_ids    = df["gym_id"].values[sorted_idx]
    p_scores   = pred_scores[sorted_idx]
    t_scores   = true_scores[sorted_idx]
    x          = np.arange(len(gym_ids))

    ax.bar(x - 0.2, t_scores, 0.38, label="Actual Score",    color=STYLE["blue"],   alpha=0.8)
    ax.bar(x + 0.2, p_scores, 0.38, label="Predicted Score", color=STYLE["accent"], alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(gym_ids, rotation=90, fontsize=7, color=STYLE["muted"])
    ax.set_ylabel("Site Score (0–100)", color=STYLE["text"])
    ax.set_title("Location Rankings: Predicted vs Actual Site Score",
                 color=STYLE["text"], fontsize=13, pad=15)

    ax.tick_params(colors=STYLE["muted"])
    for spine in ax.spines.values():
        spine.set_edgecolor(STYLE["border"])
    ax.grid(True, axis="y", color=STYLE["border"], alpha=0.4, linewidth=0.5)
    ax.legend(facecolor=STYLE["panel"], edgecolor=STYLE["border"],
              labelcolor=STYLE["text"])

    plt.tight_layout()
    out = CHARTS_VERSION / "score_ranking.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=STYLE["bg"])
    plt.close()
    print(f"  Saved → {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Model Training — XGBoost + LOO Cross-Validation")
    print("=" * 60)

    print("\n[1/6] Loading features...")
    df, manifest = load_features()
    print(f"  {len(df)} gyms, target: {MODEL_TARGET}")

    print("\n[2/6] Preparing feature matrix...")
    X, y, feature_names = prepare_matrices(df, manifest["model_input_features"])
    print(f"  X shape: {X.shape}  |  y range: {y.min():.0f}–{y.max():.0f}")

    print("\n[3/6] Running Leave-One-Out cross-validation...")
    predictions, pred_lows, pred_highs = run_loo_cv(X, y, feature_names, df)

    # Metrics
    mae  = mean_absolute_error(y, predictions)
    r2   = r2_score(y, predictions)
    mape = np.mean(np.abs((y - predictions) / (y + 1e-9))) * 100
    rmse = np.sqrt(np.mean((y - predictions) ** 2))

    print(f"\n  --- LOO CV Results ---")
    print(f"  MAE:  {mae:.1f} check-ins/day")
    print(f"  MAPE: {mape:.1f}%")
    print(f"  RMSE: {rmse:.1f}")
    print(f"  R²:   {r2:.4f}")

    v1_pass = mape <= (V1_SUCCESS_MAE_PCT * 100)
    print(f"\n  V1 Success Threshold (MAPE ≤ {V1_SUCCESS_MAE_PCT*100:.0f}%): {'PASS ✓' if v1_pass else 'NOT YET ✗'}")

    print("\n[4/6] Training final model (all 42 locations)...")
    final_model, importance = train_final_model(X, y, feature_names)

    MODELS_VERSION.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_VERSION / "xgb_model.json"
    final_model.save_model(str(model_path))
    print(f"  Model saved → {model_path}")

    # Update manifest with exact numeric features used at training time
    with open(DATA_PROCESSED / MANIFEST_FILE) as f:
        manifest_data = json.load(f)
    manifest_data["numeric_model_features"] = feature_names
    manifest_data["version"] = VERSION
    with open(DATA_PROCESSED / MANIFEST_FILE, "w") as f:
        json.dump(manifest_data, f, indent=2)

    print("\n[5/6] Generating charts...")
    pred_scores, true_scores = compute_site_scores(predictions, y)
    plot_backtest(df, predictions, pred_lows, pred_highs, mae, r2, mape)
    plot_feature_importance(importance)
    plot_score_ranking(df, pred_scores, true_scores)

    print("\n[6/6] Saving model report...")
    # Top/bottom 5 by predicted score
    df_results = df[["gym_id", "gym_name", "cluster", MODEL_TARGET]].copy()
    df_results["predicted_checkins"] = predictions.round(1)
    df_results["pred_low"]           = pred_lows.round(1)
    df_results["pred_high"]          = pred_highs.round(1)
    df_results["site_score"]         = pred_scores
    df_results["true_score"]         = true_scores
    df_results["abs_error"]          = np.abs(predictions - y).round(1)
    df_results["pct_error"]          = (np.abs(predictions - y) / (y + 1e-9) * 100).round(1)
    df_results = df_results.sort_values("site_score", ascending=False)

    results_path = DATA_PROCESSED / f"loo_predictions_{VERSION}.csv"
    df_results.to_csv(results_path, index=False)
    print(f"  Predictions saved → {results_path}")

    REPORTS_VERSION.mkdir(parents=True, exist_ok=True)
    report = {
        "version":         VERSION,
        "chain":           CHAIN_NAME,
        "n_locations":     len(df),
        "cv_strategy":     "leave-one-out",
        "model":           "XGBoost",
        "features_file":   FEATURES_FILE,
        "metrics": {
            "mae":        round(mae, 2),
            "mape_pct":   round(mape, 2),
            "rmse":       round(rmse, 2),
            "r2":         round(r2, 4),
        },
        "v1_pass":         bool(v1_pass),
        "v1_threshold_mape_pct": V1_SUCCESS_MAE_PCT * 100,
        "top_5_locations": df_results.head(5)[["gym_id", "gym_name", "site_score"]].to_dict("records"),
        "bottom_5_locations": df_results.tail(5)[["gym_id", "gym_name", "site_score"]].to_dict("records"),
        "top_10_features": list(importance.keys())[:10],
        "signal_weights_baked_in": SIGNAL_WEIGHTS,
    }

    report_path = REPORTS_VERSION / "model_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved → {report_path}")

    print("\n" + "=" * 60)
    print(f"TRAINING COMPLETE  [{VERSION.upper()}]")
    print("=" * 60)
    print(f"  MAE:       {mae:.1f} check-ins/day")
    print(f"  MAPE:      {mape:.1f}%")
    print(f"  R²:        {r2:.4f}")
    print(f"  Status:    {'PASS ✓' if v1_pass else 'NOT YET — tune model or features'}")
    print(f"\n  Charts:  outputs/{VERSION}/charts/")
    print(f"  Report:  outputs/{VERSION}/reports/model_report.json")


if __name__ == "__main__":
    main()