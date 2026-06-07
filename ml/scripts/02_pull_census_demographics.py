# =============================================================================
# scripts/pull_census_data.py
#
# Pulls real Census ACS 5-year demographic data for all census tracts
# in Maricopa County (013) and Pinal County (021), Arizona.
#
# PULL ONCE — saves to:
#   data/raw/census_tracts_maricopa.csv
#   data/raw/census_tracts_pinal.csv
#   data/raw/census_tracts_combined.csv   ← this is what the model uses
#
# COMMIT all three files to GitHub. Your partner never needs to run this.
#
# Cost: FREE (Census API has no usage fees)
# Time: ~30 seconds
#
# Get your free Census API key at:
#   https://api.census.gov/data/key_signup.html
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import requests
import pandas as pd
import time
from dotenv import load_dotenv
from config.config import *

load_dotenv(Path(__file__).parent.parent.parent / ".env")
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY", "YOUR_CENSUS_KEY_HERE")

CENSUS_BASE = "https://api.census.gov/data/2023/acs/acs5"

VARIABLES = {
    # Population
    "B01003_001E": "total_population",
    # Income
    "B19013_001E": "median_household_income",
    # Age
    "B01002_001E": "median_age",
    # Housing tenure
    "B25003_001E": "total_housing_units",
    "B25003_002E": "owner_occupied",
    "B25003_003E": "renter_occupied",
    # Education (25+)
    "B15003_001E": "pop_25_plus",
    "B15003_022E": "bachelors_degree",
    "B15003_023E": "masters_degree",
    "B15003_024E": "professional_degree",
    "B15003_025E": "doctorate_degree",
    # Age denominator
    "B01001_001E": "total_pop_age_denom",
    # Males 18-44
    "B01001_007E": "male_18_19",
    "B01001_008E": "male_20",
    "B01001_009E": "male_21",
    "B01001_010E": "male_22_24",
    "B01001_011E": "male_25_29",
    "B01001_012E": "male_30_34",
    "B01001_013E": "male_35_39",
    "B01001_014E": "male_40_44",
    # Females 18-44
    "B01001_031E": "female_18_19",
    "B01001_032E": "female_20",
    "B01001_033E": "female_21",
    "B01001_034E": "female_22_24",
    "B01001_035E": "female_25_29",
    "B01001_036E": "female_30_34",
    "B01001_037E": "female_35_39",
    "B01001_038E": "female_40_44",
}


def pull_county(state_fips: str, county_fips: str, county_name: str) -> pd.DataFrame:
    """Pull all ACS variables for every tract in a county."""
    var_string = ",".join(VARIABLES.keys())
    url = (
        f"{CENSUS_BASE}?get=NAME,{var_string}"
        f"&for=tract:*"
        f"&in=state:{state_fips}+county:{county_fips}"
        f"&key={CENSUS_API_KEY}"
    )

    print(f"  Pulling {county_name} County tracts...")
    resp = requests.get(url, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Census API error {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    headers = data[0]
    rows    = data[1:]

    df = pd.DataFrame(rows, columns=headers)

    # Rename Census variable codes to readable names
    df = df.rename(columns=VARIABLES)

    # Build GEOID (11-digit tract identifier)
    df["geoid"] = df["state"] + df["county"] + df["tract"]

    # Convert numeric columns
    numeric_cols = list(VARIABLES.values())
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Replace Census sentinel value (-666666666) with NaN
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].replace(-666666666, pd.NA)

    # Derived features
    df["pct_age_18_34"] = (
        (
            df["male_18_19"].fillna(0) + df["male_20"].fillna(0) +
            df["male_21"].fillna(0)  + df["male_22_24"].fillna(0) +
            df["male_25_29"].fillna(0) + df["male_30_34"].fillna(0) +
            df["female_18_19"].fillna(0) + df["female_20"].fillna(0) +
            df["female_21"].fillna(0)  + df["female_22_24"].fillna(0) +
            df["female_25_29"].fillna(0) + df["female_30_34"].fillna(0)
        ) / pd.to_numeric(df["total_pop_age_denom"], errors="coerce").replace(0, float("nan"))
    ).round(4)

    df["pct_age_25_44"] = (
        (
            df["male_25_29"].fillna(0)   + df["male_30_34"].fillna(0) +
            df["male_35_39"].fillna(0)   + df["male_40_44"].fillna(0) +
            df["female_25_29"].fillna(0) + df["female_30_34"].fillna(0) +
            df["female_35_39"].fillna(0) + df["female_40_44"].fillna(0)
        ) / pd.to_numeric(df["total_pop_age_denom"], errors="coerce").replace(0, float("nan"))
    ).round(4)

    df["pct_renters"] = (
        pd.to_numeric(df["renter_occupied"], errors="coerce") /
        pd.to_numeric(df["total_housing_units"], errors="coerce").replace(0, float("nan"))
    ).round(4)

    df["pct_college_plus"] = (
        (
            df["bachelors_degree"].fillna(0) + df["masters_degree"].fillna(0) +
            df["professional_degree"].fillna(0) + df["doctorate_degree"].fillna(0)
        ) / pd.to_numeric(df["pop_25_plus"], errors="coerce").replace(0, float("nan"))
    ).round(4)

    df["county_name"] = county_name

    print(f"    → {len(df)} tracts pulled")
    return df


def main():
    print("=" * 60)
    print("Census ACS Data Pull — Arizona")
    print("=" * 60)

    if CENSUS_API_KEY == "YOUR_CENSUS_KEY_HERE":
        print("\n✗ ERROR: Paste your Census API key into this script first.")
        print("  Get one free at: https://api.census.gov/data/key_signup.html")
        sys.exit(1)

    combined_path = DATA_RAW / "census_tracts_combined.csv"
    if combined_path.exists():
        print(f"\n✓ Already pulled — {combined_path} exists.")
        print("  Delete the file if you want to re-pull.")
        df = pd.read_csv(combined_path)
        print(f"  {len(df)} tracts loaded.")
        return df

    counties = [
        (STATE_FIPS, "013", "Maricopa"),
        (STATE_FIPS, "021", "Pinal"),
    ]

    all_dfs = []
    for state, county, name in counties:
        df = pull_county(state, county, name)
        out = DATA_RAW / f"census_tracts_{name.lower()}.csv"
        df.to_csv(out, index=False)
        print(f"    Saved → {out}")
        all_dfs.append(df)
        time.sleep(0.5)  # be polite to Census API

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv(combined_path, index=False)
    print(f"\n✓ Combined saved → {combined_path}")
    print(f"  Total tracts: {len(combined)}")
    print(f"  Columns: {list(combined.columns)}")

    return combined


if __name__ == "__main__":
    main()