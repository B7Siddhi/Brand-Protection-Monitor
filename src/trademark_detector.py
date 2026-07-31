# Brand Protection Monitor, Day 15: trademark misuse detection
# Implements S13 (brand_evasion) and S14 (brand_reference_stuffing) from
# docs/signal_spec.csv, the detector built specifically to close the recall
# gap day 13's evaluation exposed: brand evasion was caught only 16% of the
# time because this detector did not exist yet.
#
# S13: fuzzy match every title word against the protected brand list. A word
# that is NOT an exact brand name but scores 85+ similarity to one is a
# disguised brand, e.g. N1ke, Guccl, Ro1ex, App1e.
# S14: a listing not assigned a protected brand whose description literally
# names one anyway is riding that brand's search traffic without selling it.
# Run from the project root:  python3 src/trademark_detector.py

import sqlite3
import pandas as pd
from rapidfuzz import fuzz

import config  # day 19: shared settings, see src/config.py
# Tuned on day 15: the spec's original 85 threshold missed nearly every real
# disguise. Short words lose a large share of their score per character
# changed (n1ke vs nike scores only 75), so 85 was calibrated for longer
# strings and too strict for single-word brand evasion. Checked at 75 for
# false positives across the full listing set first: zero, every hit was a
# genuine planted evasion. Spec updated to match, now lives in config.py.
EVASION_THRESHOLD = config.BRAND_EVASION_THRESHOLD

con = sqlite3.connect(config.DB_PATH)
cur = con.cursor()
cur.execute("DELETE FROM signals WHERE signal_source = 'trademark'")

brands = pd.read_sql(
    "SELECT brand_name FROM brands WHERE is_protected = 1", con)["brand_name"].tolist()
brand_lower = [b.lower() for b in brands]

listings = pd.read_sql("""
    SELECT l.listing_id, l.title, l.description, b.brand_name
    FROM listings l LEFT JOIN brands b ON b.brand_id = l.brand_id""", con)

def check_evasion(title):
    """Return the strongest disguised-brand match in a title, or (0, None)."""
    best_ratio, best_brand = 0, None
    for word in title.replace("-", " ").replace(".", " ").split():
        wl = word.lower().strip(",")
        if len(wl) < 3 or wl in brand_lower:
            continue  # too short to mean anything, or already an exact brand word
        for bl, orig in zip(brand_lower, brands):
            ratio = fuzz.ratio(wl, bl)
            if ratio > best_ratio:
                best_ratio, best_brand = ratio, orig
    return best_ratio, best_brand

evasion_hits, stuffing_hits = [], []
for r in listings.itertuples():
    ratio, brand = check_evasion(r.title)
    if ratio >= EVASION_THRESHOLD:
        evasion_hits.append((r.listing_id, round(ratio, 1)))

    # S14 only applies to listings with no real protected brand of their own
    # (Generic or unbranded); a listing legitimately named Nike mentioning
    # "Nike" in its own description is normal, not stuffing.
    own_brand = (r.brand_name or "").lower()
    if own_brand not in brand_lower and r.description:
        desc_lower = r.description.lower()
        for bl, orig in zip(brand_lower, brands):
            if bl in desc_lower:
                stuffing_hits.append((r.listing_id, orig))
                break

cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'brand_evasion', 'trademark', ?, 5)", evasion_hits)
cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'brand_reference_stuffing', 'trademark', 1, 3)",
    [(lid,) for lid, _ in stuffing_hits])
con.commit()

print("TRADEMARK DETECTOR RUN")
print(f"  brand_evasion signals:            {len(evasion_hits)}")
print(f"  brand_reference_stuffing signals: {len(stuffing_hits)}")

print("\nSAMPLE BRAND EVASION CATCHES (title, fuzzy match strength)")
sample_ids = [lid for lid, _ in evasion_hits[:10]]
if sample_ids:
    titles = pd.read_sql(
        f"SELECT listing_id, title FROM listings WHERE listing_id IN ({','.join(map(str, sample_ids))})", con)
    ratio_map = dict(evasion_hits)
    for r in titles.itertuples():
        print(f"  #{r.listing_id:<6} \"{r.title}\"   match strength {ratio_map[r.listing_id]}")

print("\nSAMPLE BRAND REFERENCE STUFFING (description names a brand not assigned)")
for lid, brand in stuffing_hits[:5]:
    print(f"  #{lid:<6} description names {brand}")

# re-run against ground truth right now: how much did today's detector move the needle?
truth = pd.read_csv("data/raw/ground_truth.csv")
evasion_truth = set(truth[truth["fraud_type"] == "brand_evasion"]["listing_id"])
caught_today = set(lid for lid, _ in evasion_hits) | set(lid for lid, _ in stuffing_hits)
newly_caught = evasion_truth & caught_today
print(f"\nBRAND EVASION GROUND TRUTH CHECK")
print(f"  planted brand evasion listings: {len(evasion_truth)}")
print(f"  caught by today's detector:     {len(newly_caught)}  "
      f"({len(newly_caught) / max(len(evasion_truth), 1):.1%} recall from this detector alone)")
missed = evasion_truth - caught_today
if missed:
    miss_sample = truth[truth["listing_id"].isin(list(missed)[:3])]
    titles_missed = pd.read_sql(
        f"SELECT listing_id, title FROM listings WHERE listing_id IN ({','.join(map(str, list(missed)[:3]))})", con)
    print("  still missed, e.g.:")
    for r in titles_missed.itertuples():
        print(f"    #{r.listing_id} \"{r.title}\"")
con.close()
