# =============================================================================
# ml/src/common.py
#
# Shared plumbing for the StrataGym ML pipeline:
#   - config.yaml loading with absolute path resolution
#   - raw data loading (census tracts, EOS locations, competitors)
#   - the single compute_point_features() used by features.py, predict.py and
#     score_grid.py, so existing locations, dropped pins and grid cells are all
#     featurized by exactly the same code path.
#
# Not runnable on its own — imported by every other script in ml/src/.
# =============================================================================

from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree

ML_ROOT = Path(__file__).resolve().parent.parent  # .../StrataGym/ml


def fail(msg: str) -> None:
    """Fail loudly with a clear, actionable error."""
    print(f"\n✗ ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


@lru_cache(maxsize=1)
def load_config() -> dict:
    cfg_path = ML_ROOT / "config.yaml"
    if not cfg_path.exists():
        fail(f"config.yaml not found at {cfg_path}")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    # Resolve every path in cfg["paths"] relative to ml/
    cfg["paths"] = {k: ML_ROOT / v for k, v in cfg["paths"].items()}
    return cfg


def haversine_miles(lat1, lon1, lat2, lon2):
    """Vectorized haversine distance in miles."""
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return R * 2 * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# Projection: equirectangular lat/lng → miles, so cKDTree radius queries work
# in real distance units. Error over the Phoenix metro (<1°) is negligible.
# ---------------------------------------------------------------------------

_LAT0 = 33.45  # metro center latitude for the cos() correction


def to_xy_miles(lat, lng):
    x = np.asarray(lng, dtype=float) * 69.172 * math.cos(math.radians(_LAT0))
    y = np.asarray(lat, dtype=float) * 68.99
    return np.column_stack([x, y]) if np.ndim(lat) else np.array([[x, y]])


def require_columns(df: pd.DataFrame, cols: list[str], file_label: str, expects: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        fail(
            f"{file_label} is missing required column(s): {missing}\n"
            f"  Expected format: {expects}\n"
            f"  Found columns: {list(df.columns)}"
        )


# ---------------------------------------------------------------------------
# DataContext — loads all raw sources once, builds KD-trees, and exposes
# compute_point_features(lat, lng).
# ---------------------------------------------------------------------------

AGE_20_44_COLS = [
    "male_20", "male_21", "male_22_24", "male_25_29", "male_30_34",
    "male_35_39", "male_40_44",
    "female_20", "female_21", "female_22_24", "female_25_29", "female_30_34",
    "female_35_39", "female_40_44",
]


class DataContext:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or load_config()
        p = self.cfg["paths"]

        # ── Census tracts (demographics + centroids) ─────────────────────────
        for key, label in [("census_tracts", "Census ACS demographics"),
                           ("tract_centroids", "tract centroids")]:
            if not p[key].exists():
                fail(f"{label} file not found: {p[key]}\n"
                     f"  Run ml/scripts/0{'2' if key == 'census_tracts' else '3'}_* to pull it "
                     f"(see ml/src/ingest/census.py docstring).")

        census = pd.read_csv(p["census_tracts"], dtype={"geoid": str})
        centroids = pd.read_csv(p["tract_centroids"], dtype={"geoid": str})

        require_columns(
            census,
            ["geoid", "total_population", "median_household_income", "median_age",
             "pct_college_plus", "total_pop_age_denom"],
            str(p["census_tracts"]),
            "one row per census tract with ACS demographics keyed by 11-digit geoid",
        )
        require_columns(
            centroids, ["geoid", "centroid_lat", "centroid_lon", "land_area_sqmi"],
            str(p["tract_centroids"]),
            "one row per tract: geoid, centroid_lat, centroid_lon, land_area_sqmi",
        )

        # The committed ACS pull only includes age bands through 30-34.
        # ingest/census.py pulls the missing 35-44 bands into a supplemental
        # file which we merge here — required for pct_age_20_45.
        missing_bands = [c for c in AGE_20_44_COLS if c not in census.columns]
        if missing_bands:
            supp_path = p["raw_dir"] / "census_age_35_44.csv"
            if not supp_path.exists():
                fail(
                    f"Census data is missing age band column(s) {missing_bands} needed "
                    f"for pct_age_20_45, and no supplemental file exists.\n"
                    f"  Fix: python ml/src/ingest/census.py\n"
                    f"  That pulls ACS variables B01001_013E/014E/037E/038E per tract into\n"
                    f"  {supp_path} (free Census API, ~30s)."
                )
            supp = pd.read_csv(supp_path, dtype={"geoid": str})
            require_columns(
                supp, ["geoid"] + missing_bands, str(supp_path),
                "geoid plus male_35_39, male_40_44, female_35_39, female_40_44 counts",
            )
            census = census.merge(supp[["geoid"] + missing_bands], on="geoid", how="left")

        tracts = centroids.merge(census, on="geoid", how="inner")
        if len(tracts) == 0:
            fail("No tracts after joining census demographics to centroids on geoid.")

        denom = pd.to_numeric(tracts["total_pop_age_denom"], errors="coerce").replace(0, np.nan)
        age_sum = sum(tracts[c].fillna(0) for c in AGE_20_44_COLS)
        # ACS bands run 20-44; used as the practical approximation of ages 20-45
        tracts["pct_age_20_45"] = (age_sum / denom).astype(float)
        tracts["density"] = (
            tracts["total_population"] /
            tracts["land_area_sqmi"].replace(0, np.nan)
        ).fillna(0.0)

        tracts = tracts.dropna(subset=["centroid_lat", "centroid_lon"]).reset_index(drop=True)
        self.tracts = tracts
        self._tract_xy = to_xy_miles(tracts["centroid_lat"].values, tracts["centroid_lon"].values)
        self._tract_tree = cKDTree(self._tract_xy)

        # ── EOS locations ────────────────────────────────────────────────────
        if not p["eos_locations"].exists():
            fail(f"EOS locations file not found: {p['eos_locations']}")
        eos = pd.read_csv(p["eos_locations"])
        require_columns(
            eos, ["gym_id", "gym_name", "latitude", "longitude"],
            str(p["eos_locations"]),
            "one row per EOS location: gym_id, gym_name, latitude, longitude, "
            "optional grand_opening_date",
        )
        self.eos = eos.reset_index(drop=True)
        self._eos_xy = to_xy_miles(eos["latitude"].values, eos["longitude"].values)
        self._eos_tree = cKDTree(self._eos_xy)

        # ── Competitors (metro-wide sweep) ───────────────────────────────────
        if not p["competitors"].exists():
            fail(
                f"Competitor file not found: {p['competitors']}\n"
                f"  Fix: python ml/src/ingest/competitors.py\n"
                f"  That runs a metro-wide Google Places sweep (needs GOOGLE_API_KEY in .env)\n"
                f"  and writes one row per competitor gym: name, latitude, longitude, is_boutique."
            )
        comp = pd.read_csv(p["competitors"])
        require_columns(
            comp, ["name", "latitude", "longitude", "is_boutique"],
            str(p["competitors"]),
            "one row per competitor gym: name, latitude, longitude, is_boutique (0/1)",
        )
        big_box = comp[comp["is_boutique"] == 0].reset_index(drop=True)
        if len(big_box) == 0:
            fail(f"{p['competitors']} contains no non-boutique competitors — re-run the sweep.")
        self.competitors = big_box
        self._comp_xy = to_xy_miles(big_box["latitude"].values, big_box["longitude"].values)
        self._comp_tree = cKDTree(self._comp_xy)

    # -----------------------------------------------------------------------

    def compute_point_features(self, lat: float, lng: float,
                               years_open: float | None = None,
                               exclude_self_eos: bool = False) -> dict:
        """
        Compute the full model feature dict for an arbitrary lat/lng.
        exclude_self_eos: when featurizing an *existing* EOS location, don't
        count the location itself in eos_count_5mi / nearest_eos_dist_mi.
        """
        cfg = self.cfg
        xy = to_xy_miles(lat, lng)

        # Trade area demographics: population-weighted over tracts within radius
        ta_radius = cfg["trade_area"]["radius_mi"]
        idx = self._tract_tree.query_ball_point(xy[0], ta_radius)
        if not idx:
            # Point outside all tract coverage (deep desert). Everything zero.
            demo = dict(total_population=0.0, population_density=0.0,
                        median_hh_income=0.0, median_age=0.0,
                        pct_age_20_45=0.0, pct_bachelors_plus=0.0)
        else:
            t = self.tracts.iloc[idx]
            pop = t["total_population"].fillna(0).values.astype(float)
            w = pop / pop.sum() if pop.sum() > 0 else np.full(len(t), 1 / len(t))

            def wavg(col):
                vals = pd.to_numeric(t[col], errors="coerce")
                mask = vals.notna().values
                if not mask.any():
                    return 0.0
                wm = w[mask]
                return float((vals.values[mask] * wm).sum() / wm.sum()) if wm.sum() > 0 else 0.0

            demo = dict(
                total_population=float(pop.sum()),
                population_density=wavg("density"),
                median_hh_income=wavg("median_household_income"),
                median_age=wavg("median_age"),
                pct_age_20_45=wavg("pct_age_20_45"),
                pct_bachelors_plus=wavg("pct_college_plus"),
            )

        # Drive-time reachable populations (distance-radius proxy for isochrones)
        reach = {}
        for minutes, radius in cfg["trade_area"]["drive_time_radii_mi"].items():
            ridx = self._tract_tree.query_ball_point(xy[0], float(radius))
            reach[f"reachable_pop_{minutes}min"] = float(
                self.tracts.iloc[ridx]["total_population"].fillna(0).sum()) if ridx else 0.0

        # Competition
        comp_r = cfg["competition"]["competitor_radius_mi"]
        cidx = self._comp_tree.query_ball_point(xy[0], comp_r)
        nearest_comp_dist, _ = self._comp_tree.query(xy[0])

        # Same-brand cannibalization signal
        eos_r = cfg["competition"]["eos_radius_mi"]
        eidx = self._eos_tree.query_ball_point(xy[0], eos_r)
        if exclude_self_eos:
            # Drop any EOS location essentially at this point (the gym itself)
            eidx = [i for i in eidx
                    if np.linalg.norm(self._eos_xy[i] - xy[0]) > 0.05]
            dists, order = self._eos_tree.query(xy[0], k=min(2, len(self.eos)))
            dists = np.atleast_1d(dists)
            nearest_eos_dist = float(dists[1]) if len(dists) > 1 and dists[0] <= 0.05 \
                else float(dists[0])
        else:
            nearest_eos_dist, _ = self._eos_tree.query(xy[0])
            nearest_eos_dist = float(nearest_eos_dist)

        if years_open is None:
            years_open = float(cfg["synthesis"]["default_years_open"])

        return {
            **demo,
            **reach,
            "competitor_count_3mi": float(len(cidx)),
            "nearest_competitor_dist_mi": float(nearest_comp_dist),
            "eos_count_5mi": float(len(eidx)),
            "nearest_eos_dist_mi": nearest_eos_dist,
            "years_open": float(years_open),
        }

    def eos_display_names(self) -> list[str]:
        """'EOS Fitness – City [#n]' names matching the API's naming scheme."""
        def city_of(addr: str) -> str:
            parts = [s.strip() for s in str(addr).split(",")]
            return parts[1] if len(parts) >= 3 else "Arizona"

        cities = [city_of(a) for a in self.eos.get("address", [""] * len(self.eos))]
        counts: dict[str, int] = {}
        for c in cities:
            counts[c] = counts.get(c, 0) + 1
        seen: dict[str, int] = {}
        names = []
        for c in cities:
            seen[c] = seen.get(c, 0) + 1
            names.append(f"EOS Fitness – {c} #{seen[c]}" if counts[c] > 1
                         else f"EOS Fitness – {c}")
        return names


def compute_years_open(eos: pd.DataFrame, default_years: float) -> pd.Series:
    """years_open from grand_opening_date when present, else the config default."""
    if "grand_opening_date" in eos.columns:
        opened = pd.to_datetime(eos["grand_opening_date"], errors="coerce")
        years = (pd.Timestamp.today() - opened).dt.days / 365.25
        return years.fillna(default_years).clip(lower=0.0)
    return pd.Series(default_years, index=eos.index)
