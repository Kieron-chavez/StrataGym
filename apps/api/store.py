from __future__ import annotations
import csv
from config import REPO_ROOT


def _city_from_address(address: str) -> str:
    parts = [p.strip() for p in address.split(",")]
    return parts[1] if len(parts) >= 3 else "Arizona"


def _build_name(address: str, city_counts: dict[str, int], city_seen: dict[str, int]) -> str:
    city = _city_from_address(address)
    city_seen[city] = city_seen.get(city, 0) + 1
    if city_counts.get(city, 1) > 1:
        return f"EOS Fitness – {city} #{city_seen[city]}"
    return f"EOS Fitness – {city}"


def _load_gyms() -> list[dict]:
    path = REPO_ROOT / "ml" / "data" / "raw" / "eos_locations.csv"
    if not path.exists():
        raise RuntimeError("eos_locations.csv not found. Run ml/scripts/01_pull_eos_locations.py first.")

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    city_counts: dict[str, int] = {}
    for row in rows:
        city = _city_from_address(row.get("address", ""))
        city_counts[city] = city_counts.get(city, 0) + 1

    city_seen: dict[str, int] = {}
    gyms = []
    for row in rows:
        address = row.get("address", "")
        gyms.append({
            "gym_id":           row["gym_id"],
            "name":             _build_name(address, city_counts, city_seen),
            "address":          address,
            "lat":              float(row["latitude"]),
            "lng":              float(row["longitude"]),
            "status":           row.get("status", "open"),
            "monthly_members":  int(row["monthly_members"] or 0),
            "monthly_checkins": int(row["monthly_checkins"] or 0),
            "rating":           float(row["rating"]) if row.get("rating") else None,
            "review_count":     int(row["review_count"]) if row.get("review_count") else None,
        })
    return gyms


GYMS: list[dict] = _load_gyms()
