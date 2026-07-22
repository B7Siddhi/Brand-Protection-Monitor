# Brand Protection Monitor, Day 13: evaluation against ground truth
# Every listing generated on day 4 was labelled honestly: fraud or not, and if
# fraud, which type. That label was never used by any detector. Today it is
# used for exactly one purpose: grading them.
#
# Metrics:
#   precision = of the listings we alerted on, what share were truly fraud?
#               low precision means we waste investigator time on innocents.
#   recall    = of the true fraud listings, what share did we alert on?
#               low recall means fraud slips past us uninvestigated.
# Fraud teams tune thresholds to balance these deliberately; neither can be
# maximised without harming the other, and the right balance is a business
# decision, not a purely technical one.
# Run from the project root:  python3 src/evaluate.py

import sqlite3
import pandas as pd

con = sqlite3.connect("data/monitor.db")
truth = pd.read_csv("data/raw/ground_truth.csv")
truth_ids = set(truth["listing_id"])

all_listings = pd.read_sql("SELECT listing_id FROM listings", con)["listing_id"]
truth_ids = truth_ids & set(all_listings)  # only listings that survived cleaning

alerts = pd.read_sql("SELECT DISTINCT listing_id, risk_band FROM alerts", con)
alerted_ids = set(alerts["listing_id"])

tp = alerted_ids & truth_ids
fp = alerted_ids - truth_ids
fn = truth_ids - alerted_ids
tn = set(all_listings) - alerted_ids - truth_ids

precision = len(tp) / len(alerted_ids) if alerted_ids else 0
recall = len(tp) / len(truth_ids) if truth_ids else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

print("EVALUATION AGAINST GROUND TRUTH")
print(f"  planted fraud listings (post cleaning): {len(truth_ids)}")
print(f"  alerts raised (medium + high):          {len(alerted_ids)}")
print(f"  true positives  (correctly caught):     {len(tp)}")
print(f"  false positives (wrongly flagged):      {len(fp)}")
print(f"  false negatives (fraud missed):         {len(fn)}")
print(f"  true negatives  (correctly ignored):    {len(tn)}")
print(f"\n  precision: {precision:.1%}   (of alerts raised, share that were real fraud)")
print(f"  recall:    {recall:.1%}   (of real fraud, share we caught)")
print(f"  F1 score:  {f1:.3f}")

# precision and recall by risk band, this is the tuning lever for day 13
print("\nPRECISION BY RISK BAND")
for band in ["high", "medium"]:
    band_ids = set(alerts[alerts["risk_band"] == band]["listing_id"])
    band_tp = band_ids & truth_ids
    p = len(band_tp) / len(band_ids) if band_ids else 0
    print(f"  {band:<7} alerts {len(band_ids):>4}   precision {p:.1%}")

# recall by fraud type, this shows which detectors are pulling their weight
print("\nRECALL BY FRAUD TYPE")
truth_types = pd.read_csv("data/raw/ground_truth.csv")
for ftype, grp in truth_types.groupby("fraud_type"):
    type_ids = set(grp["listing_id"]) & set(all_listings)
    caught = type_ids & alerted_ids
    r = len(caught) / len(type_ids) if type_ids else 0
    print(f"  {ftype:<18} planted {len(type_ids):>4}   caught {len(caught):>4}   recall {r:.1%}")

# the false positives, worth reading individually, not just counting
print("\nSAMPLE FALSE POSITIVES (flagged but not planted as fraud)")
if fp:
    sample = pd.read_sql(f"""
        SELECT l.listing_id, s.seller_name, a.risk_score, a.risk_band
        FROM alerts a JOIN listings l ON l.listing_id = a.listing_id
        JOIN sellers s ON s.seller_id = l.seller_id
        WHERE l.listing_id IN ({','.join(map(str, list(fp)[:5]))})""", con)
    for r in sample.itertuples():
        reasons = pd.read_sql(
            f"SELECT signal_type FROM signals WHERE listing_id = {r.listing_id}", con)
        print(f"  listing {r.listing_id:<6} {r.seller_name:<20} score {r.risk_score:<6} "
              f"reasons: {', '.join(reasons['signal_type'])}")
else:
    print("  none")

# the false negatives, fraud that slipped through entirely
print("\nSAMPLE FALSE NEGATIVES (real fraud, no alert raised)")
if fn:
    sample_fn = truth_types[truth_types["listing_id"].isin(list(fn)[:5])]
    for r in sample_fn.itertuples():
        print(f"  listing {r.listing_id:<6} planted as {r.fraud_type}, never scored high enough to alert")
else:
    print("  none")

con.close()
