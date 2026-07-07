# =============================================================================
# ml/src/ingest/census.py
#
# Census ACS 5-year demographics per tract (Maricopa + Pinal County, AZ).
#
# The FULL pull already exists — ml/scripts/02_pull_census_demographics.py
# produced data/raw/census_tracts_combined.csv (committed). This script pulls
# ONLY what that file is missing: the age-35-44 bands needed to compute
# pct_age_20_45 (the committed pull stopped at age 30-34).
#
# API:      https://api.census.gov/data/2023/acs/acs5
#           ?get=B01001_013E,B01001_014E,B01001_037E,B01001_038E
#           &for=tract:*&in=state:04+county:{013|021}&key=CENSUS_API_KEY
# Auth:     CENSUS_API_KEY in StrataGym/.env (free key:
#           https://api.census.gov/data/key_signup.html)
# Produces: data/raw/census_age_35_44.csv with columns:
#           geoid, male_35_39, male_40_44, female_35_39, female_40_44
# Cost:     FREE. Never overwrites an existing output file.
#
# TODO: when re-pulling the full ACS dataset for a new metro, use
#       ml/scripts/02_pull_census_demographics.py and extend its VARIABLES
#       dict with B01001_013E/014E/037E/038E so this supplement is unneeded.
# =============================================================================

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import requests
from common import ML_ROOT, fail, load_config

try:
    from dotenv import load_dotenv
    load_dotenv(ML_ROOT.parent / ".env")
except ImportError:
    pass

CENSUS_BASE = "https://api.census.gov/data/2023/acs/acs5"
VARIABLES = {
    "B01001_013E": "male_35_39",
    "B01001_014E": "male_40_44",
    "B01001_037E": "female_35_39",
    "B01001_038E": "female_40_44",
}
STATE_FIPS = "04"
COUNTIES = ["013", "021"]  # Maricopa, Pinal


def pull_age_bands() -> pd.DataFrame:
    key = os.getenv("CENSUS_API_KEY", "")
    if not key:
        fail("CENSUS_API_KEY not set in StrataGym/.env — "
             "get a free key at https://api.census.gov/data/key_signup.html")

    frames = []
    for county in COUNTIES:
        url = (f"{CENSUS_BASE}?get={','.join(VARIABLES)}"
               f"&for=tract:*&in=state:{STATE_FIPS}+county:{county}&key={key}")
        print(f"  Pulling age 35-44 bands for county {county}...")
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            fail(f"Census API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        df = pd.DataFrame(data[1:], columns=data[0]).rename(columns=VARIABLES)
        df["geoid"] = df["state"] + df["county"] + df["tract"]
        for col in VARIABLES.values():
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        frames.append(df[["geoid"] + list(VARIABLES.values())])

    return pd.concat(frames, ignore_index=True)


def main():
    cfg = load_config()
    out_path = cfg["paths"]["raw_dir"] / "census_age_35_44.csv"
    if out_path.exists():
        print(f"✓ {out_path.name} already exists ({out_path}) — not overwriting.")
        return

    df = pull_age_bands()
    df.to_csv(out_path, index=False)
    print(f"✓ Saved → {out_path}  ({len(df)} tracts)")


if __name__ == "__main__":
    main()
