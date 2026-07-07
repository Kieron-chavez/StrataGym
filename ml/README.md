# StrataGym ML Pipeline

Site-selection and network-analytics model for EOS Fitness (44 Phoenix-metro
locations). Trains an XGBoost check-in model on **synthetic-but-grounded**
targets derived from real Census/Places data, scores arbitrary lat/lngs and a
metro-wide heatmap grid, and serves everything to the dashboard through the
FastAPI backend (`apps/api`).

Two generations live side by side:

| Where | What |
|---|---|
| `ml/src/` + `config.yaml` | **Current pipeline** (this README) |
| `ml/scripts/01–08` + `config/config.py` | Original data-pull scripts (01–05 still useful; 06–08 superseded by `ml/src/`) |

## Setup

```bash
cd ml
python3.11 -m venv .venv311          # Python 3.10+ required
.venv311/bin/pip install -r requirements.txt
```

Secrets in `StrataGym/.env`: `CENSUS_API_KEY` (free), `GOOGLE_API_KEY`
(Places API — only needed for the one-time competitor sweep).

## Run order (from the repo root)

```bash
PY=ml/.venv311/bin/python

$PY ml/src/ingest/census.py       # 1. supplemental ACS age bands (free, skips if done)
$PY ml/src/ingest/competitors.py  # 2. metro competitor sweep (~$3-5 once, skips if done)
$PY ml/src/features.py            # 3. → data/processed/features.csv (44 rows)
$PY ml/src/synthesize.py          # 4. → data/processed/training_data.csv (+ tiers)
$PY ml/src/train.py               # 5. → models/model.json + models/metrics.json
$PY ml/src/score_grid.py          # 6. → outputs/grid_scores.json + location_scores.json
                                  #      + data/grid/candidate_grid_features.csv

# Score any candidate site:
$PY ml/src/predict.py --lat 33.49 --lng -112.05
```

Every tunable constant (feature list, penetration rate, income bands, XGBoost
hyperparameters, grid bbox…) lives in `ml/config.yaml`. Nothing is hardcoded.

## What each script produces

- **features.py** — one row per EOS location: trade-area demographics
  (population-weighted census tracts within 5.5 mi), 10/15/25-min reachable
  populations (distance-radius proxy — see below), competitor counts (3 mi),
  same-brand counts (5 mi), `years_open`. Fails loudly on any missing
  file/column; never silently zero-fills.
- **synthesize.py** — `expected_checkins` target per location:
  `pop15min × penetration × income_mult × age_mult × competition_factor ×
  cannibal_factor × maturity`, ×10 visits/member/month, ×N(1, 0.12) noise.
  Prints an eyeball table plus a `synthetic_tier` (top/average/under thirds).
- **train.py** — XGBoost (depth 3, 150 trees, lr 0.05) with Leave-One-Out CV;
  saves `models/model.json` + `models/metrics.json` (LOO RMSE/R²/feature
  importances); warns on any location off by >40% (data-problem flag).
- **explain.py** — `get_score_drivers(feature_row)` → top-4 SHAP drivers as
  `{label, points (−30…+30), direction}`. Uses `shap.TreeExplainer`, falling
  back to XGBoost's native `pred_contribs` (identical TreeSHAP) when shap
  isn't installed — that's what keeps the API server dependency-light.
- **predict.py** — full site report for any lat/lng: opportunity score
  (percentile vs the 44 network predictions), projected check-ins, distance-
  decay cannibalization vs nearby EOS gyms, net network impact, SHAP drivers.
  Importable (`score_point`) and CLI.
- **score_grid.py** — ~1,850 in-market grid cells (0.015° ≈ 1 mi) scored for
  the heatmap; desert cells (<25k reachable pop) are excluded so XGBoost
  can't extrapolate hot zones into the desert. Also writes the 44-location
  scores/tiers/drivers that drive pin colors and the Location Profile panel.

## Serving to the frontend

`apps/api` (FastAPI) imports `ml/src/predict.py` directly:

- `POST /api/score-location` → real `score_point()` (stub fallback if the
  pipeline hasn't been run)
- `GET /api/gyms` → merges `tier` / `opportunity_score` / `predicted_checkins`
  from `outputs/location_scores.json`
- `GET /api/grid-scores` → serves `outputs/grid_scores.json` for the
  Opportunity Heatmap layer

After re-running the pipeline, just restart (or redeploy) the API — it reads
the fresh artifacts from disk.

## Known approximations

1. **Drive-time populations** are straight-line radii (3.5 / 5.5 / 10.5 mi for
   10/15/25 min) over tract centroids, not true isochrones. Swap in real
   isochrones via `ml/src/ingest/drive_time.py` (stub documents the exact
   Mapbox API + plan).
2. **pct_age_20_45** is ACS ages 20–44 (band boundaries).
3. **Absolute check-in volumes** are driven by `synthesis.penetration_rate`
   (0.09). Rankings/scores are scale-invariant; if you want realistic absolute
   member counts (~5–8k/club), drop it to ~0.02 and re-run steps 4–6.

## Swapping in real EOS data later

The architecture doesn't change — only the target column.

**Option A — real performance numbers** (check-ins/membership per location):
1. Add a `monthly_checkins` column keyed by `gym_id` (CSV from EOS).
2. In `training_data.csv`, replace `expected_checkins` with it (or point
   `train.py`'s `TARGET` at the new column).
3. Re-run `train.py` + `score_grid.py`. Everything downstream (percentile
   scores, SHAP drivers, cannibalization, heatmap) works unchanged.
4. Optional: compute real `years_open` by filling `grand_opening_date` in
   `data/raw/eos_locations.csv`.

**Option B — tier rankings only** (EOS will say "these are our top/bottom
clubs" but not share numbers):
1. Keep the synthetic magnitude machinery, but calibrate it: order the
   synthetic `expected_checkins` so its terciles match EOS's stated tiers
   (e.g. rank-map synthetic values onto the EOS ordering, or fit
   `synthesis.*` coefficients until `synthetic_tier` agrees with their list).
2. Re-run steps 4–6. The model then learns *which demographics separate their
   real top clubs from their real bottom clubs* even without absolute numbers.

## Committing artifacts

`data/raw/`, `data/processed/`, `models/` and `outputs/` are all committed —
teammates and the deployed API never need API keys or a re-run.
