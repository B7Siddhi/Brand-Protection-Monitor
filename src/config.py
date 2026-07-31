# Brand Protection Monitor, shared configuration
# Day 19: a single source of truth for values that were previously
# duplicated and hardcoded across multiple files. Before today, AS_OF was
# copy-pasted identically into two separate detectors, and "data/monitor.db"
# appeared as a literal string in ten different files. Change a threshold
# here now, and every script that matters picks it up automatically.

DB_PATH = "data/monitor.db"
SCHEMA_PATH = "src/schema.sql"

# Analysis date used for account age and review velocity calculations.
# Kept deliberately separate from generate_data.py's own TODAY constant:
# that one drives the fixed-seed synthetic data itself and must never
# change, or every listing ID, screenshot, and the day 14 case report
# would shift under it.
AS_OF_DATE = "2026-07-07"

# Composite risk score bands (src/risk_scorer.py)
RISK_HIGH = 12
RISK_MEDIUM = 6

# Fuzzy brand name matching (src/trademark_detector.py), tuned day 15:
# short words lose more score per character changed than long ones, so 75
# catches real disguises (n1ke, guccl) that the original 85 spec value missed.
BRAND_EVASION_THRESHOLD = 75

# Review fraud text similarity (src/review_signals.py)
REVIEW_SIMILARITY_THRESHOLD = 0.9
REVIEW_MIN_COPIES = 3
