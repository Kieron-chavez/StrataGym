# =============================================================================
# config/config.py
# Central configuration for the entire project.
# Change values here — they propagate everywhere.
# =============================================================================

from pathlib import Path

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DATA_RAW        = ROOT / "data" / "raw"
DATA_PROCESSED  = ROOT / "data" / "processed"
DATA_SYNTHETIC  = ROOT / "data" / "synthetic"
MODELS_DIR      = ROOT / "models"
OUTPUTS_CHARTS  = ROOT / "outputs" / "charts"
OUTPUTS_REPORTS = ROOT / "outputs" / "reports"

# -----------------------------------------------------------------------------
# Chain identity (swap this when onboarding a new customer)
# -----------------------------------------------------------------------------
CHAIN_NAME       = "EOS_SYNTHETIC"   # used in filenames and report headers
N_LOCATIONS      = 42
STATE_FIPS       = "04"              # Arizona
COUNTIES         = ["013", "021"]    # Maricopa, Pinal

# -----------------------------------------------------------------------------
# Gym profile (reflects EOS footprint)
# -----------------------------------------------------------------------------
SQFT_RANGE       = (18_000, 45_000)  # typical big-box gym range
TIERS            = ["Standard", "Black Card"]
TIER_WEIGHTS     = [0.4, 0.6]        # 60% Black Card locations
BASE_DUES        = {"Standard": 9.99, "Black Card": 24.99}
AMENITIES_POOL   = [
    "pool", "sauna", "kids_club", "turf", "cinema_cardio",
    "basketball", "racquetball", "smoothie_bar", "tanning"
]

# -----------------------------------------------------------------------------
# Trade area definition
# -----------------------------------------------------------------------------
TRADE_AREA_MINUTES = 15     # drive-time cutoff
COMPETITOR_RADII   = [3, 5] # miles for competitor counts

# -----------------------------------------------------------------------------
# Synthetic data parameters
# -----------------------------------------------------------------------------
RANDOM_SEED         = 42
HISTORY_YEARS       = 3
CHECKIN_BASE_RANGE  = (400, 1_400)   # mature daily check-ins min/max
RAMP_UP_MONTHS      = 6              # months to reach full maturity

# Performance signal weights (must sum to 1.0)
# These are what we bake in — model should rediscover them
SIGNAL_WEIGHTS = {
    "income_score":             0.30,
    "age_18_34_score":          0.25,
    "competition_penalty":      0.20,
    "cannibalization_penalty":  0.15,
    "retail_density_score":     0.10,
}

# -----------------------------------------------------------------------------
# Model
# -----------------------------------------------------------------------------
MODEL_TARGET     = "avg_daily_checkins_12mo"
CV_STRATEGY      = "loo"          # leave-one-out
PREDICTION_ALPHA = 0.80           # 80% prediction interval

XGBOOST_PARAMS = {
    "n_estimators":     300,
    "max_depth":        3,         # shallow — prevents overfitting on 42 samples
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "random_state":     RANDOM_SEED,
    "verbosity":        0,
}

# MAE threshold for V1 success (as % of mean target)
V1_SUCCESS_MAE_PCT = 0.20   # within 20% = pass

# -----------------------------------------------------------------------------
# Arizona bounding box (for synthetic coordinate generation)
# Maricopa + Pinal county approximate bounds
# -----------------------------------------------------------------------------
AZ_LAT_RANGE = (32.50, 33.85)
AZ_LON_RANGE = (-112.55, -111.35)

# Known Arizona metro clusters for realistic gym placement
AZ_CLUSTERS = [
    # (name, center_lat, center_lon, radius_deg, n_gyms)
    ("Phoenix",       33.4484, -112.0740, 0.25, 12),
    ("Mesa",          33.4152, -111.8315, 0.18, 8),
    ("Chandler",      33.3062, -111.8413, 0.15, 6),
    ("Scottsdale",    33.4942, -111.9261, 0.18, 6),
    ("Tempe",         33.4255, -111.9400, 0.12, 4),
    ("Gilbert",       33.3528, -111.7890, 0.15, 4),
    ("Peoria",        33.5806, -112.2374, 0.15, 2),
]   # total = 42