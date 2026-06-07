from __future__ import annotations
import math
from fastapi import APIRouter
from schemas import ScoreRequest
from store import GYMS

router = APIRouter()


@router.post("/api/score-location")
def score_location(body: ScoreRequest):
    def _dist(g: dict) -> float:
        dlat = body.lat - g["lat"]
        dlng = body.lng - g["lng"]
        return math.sqrt(dlat**2 + (dlng * math.cos(math.radians(body.lat)))**2) * 69.0

    nearby = sorted(
        [{"gym_id": g["gym_id"], "name": g["name"], "lat": g["lat"], "lng": g["lng"],
          "distance_miles": round(_dist(g), 1)} for g in GYMS],
        key=lambda x: x["distance_miles"],
    )
    return {
        "lat": body.lat, "lng": body.lng,
        "opportunity_score": 82, "projected_checkins": 8760,
        "cannibalization_risk": 24, "net_network_impact": 5420,
        "nearby_gyms": nearby[:3],
    }
