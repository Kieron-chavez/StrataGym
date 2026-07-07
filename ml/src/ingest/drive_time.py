# =============================================================================
# ml/src/ingest/drive_time.py  — STUB
#
# Real drive-time isochrone populations (10/15/25 min) per location/grid cell.
#
# Currently the pipeline approximates reachable populations with straight-line
# radii over census tract centroids (config.yaml → trade_area.drive_time_radii_mi,
# implemented in common.DataContext.compute_point_features). This stub is where
# real isochrones plug in later.
#
# API:      Mapbox Isochrone API (the frontend already uses it for map overlays)
#           GET https://api.mapbox.com/isochrone/v1/mapbox/driving/{lng},{lat}
#               ?contours_minutes=10,15,25&polygons=true
#               &access_token=NEXT_PUBLIC_MAPBOX_TOKEN
#           Alternative: Google Routes API distance matrix from each point to
#           tract centroids (see ml/scripts/05_pull_drive_times.py).
# Auth:     NEXT_PUBLIC_MAPBOX_TOKEN in StrataGym/.env (Mapbox), or
#           GOOGLE_API_KEY (Google Routes).
# Produces: data/raw/drive_time_populations.csv with columns:
#           point_id, latitude, longitude,
#           reachable_pop_10min, reachable_pop_15min, reachable_pop_25min
#           (population = sum of tract populations whose centroid falls inside
#            each isochrone polygon; point-in-polygon via shapely)
#
# TODO: implement pull_isochrone_populations() —
#   1. Call Mapbox Isochrone (contours_minutes=10,15,25) per point; free tier
#      is 300 req/min, 100k/mo — 44 locations + ~600 grid cells fits easily.
#   2. Point-in-polygon test tract centroids against each contour (shapely).
#   3. Sum tract total_population per contour, write the CSV above.
#   4. In common.py, prefer this file over the radius proxy when it exists.
# NOTE: never overwrite data/raw/drive_time_populations.csv if it already
#       exists — skip and print a message, like the other ingest scripts.
# =============================================================================

from __future__ import annotations

import pandas as pd


def pull_isochrone_populations(points: pd.DataFrame) -> pd.DataFrame:
    """
    points: DataFrame with columns point_id, latitude, longitude.
    Returns DataFrame with reachable_pop_{10,15,25}min per point.
    """
    raise NotImplementedError(
        "Real isochrone ingestion not implemented yet — the pipeline uses the "
        "distance-radius proxy in common.compute_point_features(). See TODO above."
    )


if __name__ == "__main__":
    print(__doc__)
