# =============================================================================
# ml/src/synthesize.py
#
# Generates the synthetic-but-grounded training target (expected_checkins) for
# each EOS location from real demographic inputs, using known fitness-industry
# relationships. Writes data/processed/training_data.csv.
#
# Swap in real EOS performance data later without touching the architecture —
# see ml/README.md ("Swapping in real EOS data").
#
# Run from project root:  python ml/src/synthesize.py
# =============================================================================

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from common import fail, load_config


def income_multiplier(income: float, bands: list) -> float:
    """Piecewise multiplier on median household income (bands from config)."""
    for upper, mult in bands:
        if income < float(upper):
            return float(mult)
    return float(bands[-1][1])


def synthesize(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    s = cfg["synthesis"]
    rng = np.random.default_rng(s["random_seed"])

    # 1. Base membership pool from 15-min reachable population
    base_membership = df["reachable_pop_15min"] * s["penetration_rate"]

    # 2. Income sweet spot (55k-90k for value gym brands like EOS)
    inc_mult = df["median_hh_income"].apply(
        lambda v: income_multiplier(v, s["income_multipliers"]))

    # 3. Prime gym demographic (ages 20-45)
    age_mult = df["pct_age_20_45"] / s["prime_age_baseline"]

    # 4. Competition dampening
    comp_factor = 1.0 / (1.0 + s["competition_penalty"] * df["competitor_count_3mi"])

    # 5. Same-brand cannibalization dampening
    cann_factor = 1.0 / (1.0 + s["cannibal_penalty"] * df["eos_count_5mi"])

    # 6. Maturity ramp — new locations haven't hit full membership yet
    maturity = (df["years_open"] / s["maturity_years_to_full"]).clip(upper=1.0)

    # 7-8. Expected members → expected monthly check-ins
    expected_members = (base_membership * inc_mult * age_mult
                        * comp_factor * cann_factor * maturity)
    expected_checkins = expected_members * s["avg_monthly_visits"]

    # 9. Multiplicative gaussian noise, clipped non-negative
    noise = rng.normal(1.0, s["noise_std"], size=len(df))
    expected_checkins = np.clip(expected_checkins * noise, 0, None)

    out = df.copy()
    out["_base_membership"] = base_membership.round(0)
    out["_income_mult"] = inc_mult.round(3)
    out["_age_mult"] = age_mult.round(3)
    out["_comp_factor"] = comp_factor.round(3)
    out["_cann_factor"] = cann_factor.round(3)
    out["_maturity"] = maturity.round(3)
    out["expected_members"] = expected_members.round(0).astype(int)
    # 10. Integer target
    out["expected_checkins"] = expected_checkins.round(0).astype(int)

    # Tier: top third / middle / bottom third — drives pin colors on the map
    q_lo, q_hi = out["expected_checkins"].quantile(cfg["synthesis"]["tier_quantiles"])
    out["synthetic_tier"] = np.select(
        [out["expected_checkins"] >= q_hi, out["expected_checkins"] <= q_lo],
        ["top", "under"], default="average",
    )
    return out


def main():
    cfg = load_config()
    feats_path = cfg["paths"]["features"]
    if not feats_path.exists():
        fail(f"{feats_path} not found — run: python ml/src/features.py")

    df = pd.read_csv(feats_path)
    missing = [c for c in cfg["feature_columns"] if c not in df.columns]
    if missing:
        fail(f"features.csv is missing column(s) {missing} — re-run features.py")

    print("=" * 70)
    print("synthesize.py — grounded synthetic target generation")
    print("=" * 70)

    out = synthesize(df, cfg)
    out_path = cfg["paths"]["training_data"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"\n✓ Saved → {out_path}  ({len(out)} rows)")

    # Eyeball table: name, key inputs, synthetic output
    print("\nPer-location summary (sorted by expected_checkins):")
    view = out[[
        "name", "reachable_pop_15min", "median_hh_income", "pct_age_20_45",
        "competitor_count_3mi", "eos_count_5mi",
        "_income_mult", "_age_mult", "_comp_factor", "_cann_factor",
        "expected_members", "expected_checkins", "synthetic_tier",
    ]].sort_values("expected_checkins", ascending=False)
    view = view.rename(columns={
        "reachable_pop_15min": "pop15min", "median_hh_income": "income",
        "pct_age_20_45": "pct20_45", "competitor_count_3mi": "comp3mi",
        "eos_count_5mi": "eos5mi", "expected_members": "members",
        "expected_checkins": "checkins", "synthetic_tier": "tier",
    })
    with pd.option_context("display.width", 200, "display.max_rows", None,
                           "display.float_format", "{:,.2f}".format):
        print(view.to_string(index=False))

    print(f"\nTier counts: {out['synthetic_tier'].value_counts().to_dict()}")
    print(f"Check-ins range: {out['expected_checkins'].min():,} – "
          f"{out['expected_checkins'].max():,} / month")


if __name__ == "__main__":
    main()
