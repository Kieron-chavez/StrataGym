import csv
import math
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="StrataGym API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GYM_MASTER_PATH = (
    Path(__file__).parent.parent.parent / "ml" / "data" / "raw" / "eos_locations.csv"
)


def _city_from_address(address: str) -> str:
    """'3005 N Dysart Rd, Avondale, AZ 85392, USA' → 'Avondale'"""
    parts = [p.strip() for p in address.split(",")]
    return parts[1] if len(parts) >= 3 else "Arizona"


def _build_name(address: str, city_counts: dict[str, int],
                city_seen: dict[str, int]) -> str:
    city = _city_from_address(address)
    city_seen[city] = city_seen.get(city, 0) + 1
    if city_counts.get(city, 1) > 1:
        return f"EOS Fitness – {city} #{city_seen[city]}"
    return f"EOS Fitness – {city}"


def load_gyms() -> list[dict]:
    if not GYM_MASTER_PATH.exists():
        raise RuntimeError(
            f"gym_master.csv not found at {GYM_MASTER_PATH}. "
            "Run ml/scripts/pull_eos_locations.py first."
        )

    rows = []
    with open(GYM_MASTER_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Count gyms per city to decide whether to add # suffix
    city_counts: dict[str, int] = {}
    for row in rows:
        city = _city_from_address(row.get("address", ""))
        city_counts[city] = city_counts.get(city, 0) + 1

    city_seen: dict[str, int] = {}
    gyms = []
    for row in rows:
        address = row.get("address", "")
        name = _build_name(address, city_counts, city_seen)
        gyms.append({
            "gym_id":          row["gym_id"],
            "name":            name,
            "address":         address,
            "lat":             float(row["latitude"]),
            "lng":             float(row["longitude"]),
            "status":          row.get("status", "open"),
            "monthly_members": int(row["monthly_members"] or 0),
            "monthly_checkins": int(row["monthly_checkins"] or 0),
            "rating":          float(row["rating"]) if row.get("rating") else None,
            "review_count":    int(row["review_count"]) if row.get("review_count") else None,
        })

    return gyms


# Load once at startup — reload the server to pick up CSV changes
GYMS = load_gyms()


class ScoreRequest(BaseModel):
    lat: float
    lng: float


@app.get("/api/gyms")
def get_gyms():
    return {"gyms": GYMS}


@app.post("/api/score-location")
def score_location(body: ScoreRequest):
    def _dist(g: dict) -> float:
        dlat = body.lat - g["lat"]
        dlng = body.lng - g["lng"]
        # Haversine-approximation in miles (accurate enough for AZ metro)
        return math.sqrt(dlat**2 + (dlng * math.cos(math.radians(body.lat)))**2) * 69.0

    nearby = sorted(
        [
            {
                "gym_id": g["gym_id"],
                "name": g["name"],
                "lat": g["lat"],
                "lng": g["lng"],
                "distance_miles": round(_dist(g), 1),
            }
            for g in GYMS
        ],
        key=lambda x: x["distance_miles"],
    )

    return {
        "lat": body.lat,
        "lng": body.lng,
        "opportunity_score": 82,
        "projected_checkins": 8760,
        "cannibalization_risk": 24,
        "net_network_impact": 5420,
        "nearby_gyms": nearby[:3],
    }
