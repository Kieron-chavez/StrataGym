# ML Pipeline

This directory is where the StrataGym ML pipeline lives.

## Planned Components

- **Member density modeling** — spatial clustering of check-in data to generate heatmap inputs
- **Drive-time isochrone generation** — compute drive-time polygons from candidate lat/lng coordinates
- **Opportunity scoring model** — ensemble model combining member density, competitor proximity, demographics, and traffic patterns to produce `opportunity_score`
- **Cannibalization estimator** — predicts member overlap between an existing and proposed location
- **Demand forecasting** — time-series model for projecting monthly check-ins at new sites

## Tech Stack (planned)

- Python 3.11+
- scikit-learn / XGBoost for tabular models
- GeoPandas + Shapely for spatial operations
- OSRM or Valhalla for drive-time routing
- MLflow for experiment tracking

## Status

> Placeholder — ML pipeline not yet implemented. See `apps/api` for hardcoded stub responses used during early development.
