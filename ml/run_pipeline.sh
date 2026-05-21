#!/bin/bash
# =============================================================================
# run_pipeline.sh  —  Full EOS Fitness Site Intelligence Pipeline
#
# Pulls real data → builds features → trains model → scores a candidate site.
# Each pull step skips itself if output already exists — safe to re-run.
# After first run, commit data/raw/ so teammates never need API keys.
#
# Usage: bash run_pipeline.sh
#
# Prerequisites:
#   .env at repo root with GOOGLE_API_KEY and CENSUS_API_KEY
#   Google APIs enabled: Places, Distance Matrix
# =============================================================================

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   StrataGym ML  —  EOS SITE INTELLIGENCE        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

echo "▶ Step 1: Pull real EOS Fitness locations from Google Places"
"$PYTHON" scripts/01_pull_eos_locations.py
echo ""

echo "▶ Step 2: Pull Census ACS demographics (FREE — skips if done)"
"$PYTHON" scripts/02_pull_census_demographics.py
echo ""

echo "▶ Step 3: Pull Census tract centroids (FREE — skips if done)"
"$PYTHON" scripts/03_pull_tract_centroids.py
echo ""

echo "▶ Step 4: Pull Google Places — competitors + POIs (~\$12, skips if done)"
"$PYTHON" scripts/04_pull_competitors_and_pois.py
echo ""

echo "▶ Step 5: Pull Google Distance Matrix — drive times (~\$45, skips if done)"
"$PYTHON" scripts/05_pull_drive_times.py
echo ""

echo "▶ Step 6: Build feature matrix"
"$PYTHON" scripts/06_build_feature_matrix.py
echo ""

echo "▶ Step 7: Train model + back-test"
"$PYTHON" scripts/07_train_model.py \
  --features-file model_features.csv \
  --manifest-file feature_manifest.json
echo ""

echo "▶ Step 8: Score example candidate location"
"$PYTHON" scripts/08_score_new_location.py \
  --features-file model_features.csv \
  --manifest-file feature_manifest.json
echo ""

echo "╔══════════════════════════════════════════════════╗"
echo "║  PIPELINE COMPLETE                               ║"
echo "║  Charts  → outputs/charts/                      ║"
echo "║  Reports → outputs/reports/                     ║"
echo "║  Model   → models/xgb_model.json                ║"
echo "║                                                  ║"
echo "║  Commit data/raw/ — teammates skip the pulls.   ║"
echo "╚══════════════════════════════════════════════════╝"
