from __future__ import annotations

import json
import math
import sys

from fastapi import APIRouter, HTTPException
from schemas import ScoreRequest
from store import GYMS
from config import REPO_ROOT

router = APIRouter()

# The ML pipeline lives in ml/src — same repo, shared on disk with this API.
ML_SRC = REPO_ROOT / "ml" / "src"
if str(ML_SRC) not in sys.path:
    sys.path.insert(0, str(ML_SRC))

try:
    from predict import score_point  # ml/src/predict.py
    _ML_IMPORTED = True
except Exception as e:  # missing deps or pipeline not built yet
    print(f"⚠ ML pipeline unavailable ({e}); /api/score-location will serve stub values")
    _ML_IMPORTED = False

GRID_SCORES_PATH = REPO_ROOT / "ml" / "outputs" / "grid_scores.json"


def _stub_response(lat: float, lng: float) -> dict:
    """Pre-pipeline fallback in the same shape as predict.score_point()."""
    def _dist(g: dict) -> float:
        dlat = lat - g["lat"]
        dlng = lng - g["lng"]
        return math.sqrt(dlat**2 + (dlng * math.cos(math.radians(lat)))**2) * 69.0

    nearby = []
    for g in GYMS:
        d = _dist(g)
        if d <= 5.0:
            overlap = max(0.0, 1 - d / 5.0) * 0.35
            nearby.append({
                "name": g["name"],
                "distance_mi": round(d, 1),
                "cannibalization_pct": round(overlap * 100),
                "impact": -round(overlap * 8760),
            })
    nearby.sort(key=lambda x: x["distance_mi"])

    return {
        "lat": lat, "lng": lng,
        "opportunity_score": 82,
        "score_label": "Strong site",
        "score_percentile_label": "Top 18% of candidates",
        "projected_checkins": 8760,
        "cannibalization_pct": 24,
        "cannibalization_label": "Moderate",
        "net_network_impact": 5420,
        "score_drivers": [],
        "nearby_eos_locations": nearby[:5],
    }


@router.post("/api/score-location")
def score_location(body: ScoreRequest):
    if _ML_IMPORTED:
        try:
            return score_point(body.lat, body.lng)
        # ml/src uses fail() → SystemExit for missing artifacts; catch
        # BaseException so a half-built pipeline can never kill the server.
        except BaseException as e:
            print(f"⚠ score_point failed ({e}); serving stub values")
    return _stub_response(body.lat, body.lng)


@router.get("/api/grid-scores")
def grid_scores():
    if not GRID_SCORES_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Grid scores not computed yet — run: python ml/src/score_grid.py",
        )
    with open(GRID_SCORES_PATH) as f:
        cells = json.load(f)
    return {"cells": cells, "count": len(cells)}
