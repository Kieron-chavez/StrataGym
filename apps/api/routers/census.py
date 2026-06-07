from __future__ import annotations
import pandas as pd
from fastapi import APIRouter, HTTPException
from config import REPO_ROOT

router = APIRouter()


@router.get("/api/census-density")
def get_census_density():
    census_path    = REPO_ROOT / "ml" / "data" / "raw" / "census_tracts_combined.csv"
    centroids_path = REPO_ROOT / "ml" / "data" / "raw" / "tract_centroids_az.csv"

    if not census_path.exists() or not centroids_path.exists():
        raise HTTPException(status_code=404, detail="Census data not available")

    census    = pd.read_csv(census_path, dtype={"geoid": str})
    centroids = pd.read_csv(centroids_path, dtype={"geoid": str})

    merged = centroids.merge(
        census[["geoid", "total_population", "pct_age_18_34", "median_household_income"]],
        on="geoid", how="left",
    ).dropna(subset=["centroid_lat", "centroid_lon", "pct_age_18_34"])

    # NaN is truthy in Python — "nan or 0" returns nan, and int(nan) throws ValueError
    merged = merged.fillna({"total_population": 0, "median_household_income": 0})

    tracts = [
        {
            "lat":           round(float(row.centroid_lat), 6),
            "lng":           round(float(row.centroid_lon), 6),
            "population":    int(row.total_population),
            "pct_age_18_34": round(float(row.pct_age_18_34), 4),
            "median_income": int(row.median_household_income),
        }
        for row in merged.itertuples()
    ]

    return {"tracts": tracts, "count": len(tracts)}
