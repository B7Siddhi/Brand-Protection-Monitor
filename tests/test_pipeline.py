# Brand Protection Monitor, Day 19: automated tests
# Six tests, cheapest and fastest first. The first four are unit tests: they
# check one piece of logic in isolation, in well under a second each, so
# they can be run constantly while developing. The last two are integration
# tests: they actually run pipeline scripts as subprocesses against real
# (tiny, or full) data, because some bugs only show up when the pieces run
# together, not when each is checked alone. Both kinds matter; neither
# replaces the other.
# Run from the project root:  python3 -m pytest tests/ -v

import csv
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
import config  # noqa: E402  (must come after sys.path is set up)


# ---------------- unit tests ----------------

def test_schema_creates_five_tables():
    """schema.sql should build exactly the five tables the pipeline expects."""
    con = sqlite3.connect(":memory:")
    con.executescript((SRC / "schema.sql").read_text())
    tables = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert tables == {"sellers", "brands", "listings", "signals", "alerts"}


def test_config_thresholds_are_sane():
    """Catches an easy mistake: bands or thresholds accidentally swapped or
    set out of range when someone edits config.py in future."""
    assert config.RISK_MEDIUM < config.RISK_HIGH
    assert 0 < config.BRAND_EVASION_THRESHOLD <= 100
    assert 0 < config.REVIEW_SIMILARITY_THRESHOLD <= 1
    assert config.REVIEW_MIN_COPIES >= 2


def test_brand_evasion_threshold_catches_known_disguises():
    """The exact tuning question day 15 answered by hand: does the threshold
    in config.py still separate real disguises from ordinary words? Uses the
    same disguises generate_data.py plants (N1ke, Guccl, Ro1ex, App1e)."""
    real_brands = ["nike", "gucci", "rolex", "apple"]
    disguises = ["n1ke", "guccl", "ro1ex", "app1e"]
    for word, brand in zip(disguises, real_brands):
        ratio = fuzz.ratio(word, brand)
        assert ratio >= config.BRAND_EVASION_THRESHOLD, (
            f"{word} scored {ratio} against {brand}, below the configured threshold")

    # an unrelated, ordinary word should not accidentally clear the bar
    # against any protected brand name
    ordinary = "trainers"
    for brand in real_brands:
        ratio = fuzz.ratio(ordinary, brand)
        assert ratio < config.BRAND_EVASION_THRESHOLD, (
            f"'{ordinary}' scored {ratio} against {brand}, that would be a false positive")


def test_risk_band_boundaries():
    """Reproduces risk_scorer.py's exact pd.cut call on a handful of scores
    chosen right at the band edges, since boundary bugs (is 6 medium or low?)
    are the easiest kind of scoring bug to ship unnoticed."""
    scores = pd.Series([0, 5.99, 6, 11.99, 12, 50])
    bands = pd.cut(scores,
                    bins=[0, config.RISK_MEDIUM, config.RISK_HIGH, float("inf")],
                    labels=["low", "medium", "high"], right=False)
    assert list(bands) == ["low", "low", "medium", "medium", "high", "high"]


# ---------------- integration tests ----------------

@pytest.fixture
def tiny_project(tmp_path):
    """Builds a miniature copy of the real project: real scripts and schema,
    but four hand written listings instead of 1098 generated ones, so
    clean_load.py's actual rejection logic can be checked against known
    right answers in under a second."""
    proj = tmp_path / "tiny"
    (proj / "src").mkdir(parents=True)
    (proj / "data" / "raw").mkdir(parents=True)
    for f in ["schema.sql", "clean_load.py", "config.py"]:
        shutil.copy(SRC / f, proj / "src" / f)

    raw = proj / "data" / "raw"
    with open(raw / "sellers_raw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seller_id", "seller_name", "join_date", "country", "is_authorised"])
        w.writerow([1, "seller_ok", "2026-01-01", "GB", 1])

    with open(raw / "brands.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["brand_name", "is_protected", "rrp_min", "rrp_max"])
        w.writerow(["Nike", 1, 60, 180])

    with open(raw / "listings_raw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["listing_id", "seller_id", "brand", "title", "description",
                     "category", "price", "currency", "listed_date",
                     "review_count", "avg_rating", "image_ref"])
        # one clean row, and one that must be rejected: a negative price
        w.writerow([1, 1, "Nike", "Genuine Nike Trainers", "desc", "Trainers",
                    80, "GBP", "2026-06-01", 5, 4.5, "img_1"])
        w.writerow([2, 1, "Nike", "Genuine Nike Trainers", "desc", "Trainers",
                    -10, "GBP", "2026-06-01", 5, 4.5, "img_2"])

    with open(raw / "reviews_raw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["review_id", "listing_id", "rating", "review_text", "review_date"])
        w.writerow([1, 1, 5, "Good product", "2026-06-05"])

    return proj


def test_clean_load_rejects_negative_price(tiny_project):
    """Runs the real clean_load.py against the two-row fixture above and
    checks it did what day 5's cleaning rules promise: keep the good listing,
    reject the negative price with the right reason, in the rejects log."""
    result = subprocess.run(
        [sys.executable, "src/clean_load.py"],
        cwd=tiny_project, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    con = sqlite3.connect(tiny_project / "data" / "monitor.db")
    remaining_ids = [r[0] for r in con.execute("SELECT listing_id FROM listings")]
    con.close()
    assert remaining_ids == [1]

    rejects = pd.read_csv(tiny_project / "data" / "rejects_log.csv")
    rejected_row = rejects[rejects["listing_id"] == 2]
    assert len(rejected_row) == 1
    assert rejected_row.iloc[0]["reason"] == "non positive price"


def test_full_pipeline_run_hits_expected_recall(tmp_path):
    """The 'verify a clean end to end run' check: delete any existing
    database, run the real run_pipeline.py against the real, full synthetic
    dataset, and confirm it lands where days 4 to 18 already proved it
    should, 100% recall and a substantial alert queue. If a future change
    silently breaks a detector, this is the test that catches it."""
    proj = tmp_path / "full"
    shutil.copytree(SRC, proj / "src")
    (proj / "data").mkdir()
    (proj / "docs").mkdir()  # network_analysis.py saves its cluster chart here

    result = subprocess.run(
        [sys.executable, "src/run_pipeline.py"],
        cwd=proj, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]

    con = sqlite3.connect(proj / "data" / "monitor.db")
    n_alerts = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    con.close()
    assert n_alerts > 100, "expected a substantial alert queue on the full synthetic dataset"

    truth = pd.read_csv(proj / "data" / "raw" / "ground_truth.csv")
    con = sqlite3.connect(proj / "data" / "monitor.db")
    alerted_ids = {r[0] for r in con.execute("SELECT DISTINCT listing_id FROM alerts")}
    all_listing_ids = {r[0] for r in con.execute("SELECT listing_id FROM listings")}
    con.close()
    truth_ids = set(truth["listing_id"]) & all_listing_ids
    recall = len(truth_ids & alerted_ids) / len(truth_ids)
    assert recall == 1.0, f"recall dropped to {recall:.1%}, expected 100% as measured on day 13/15"
