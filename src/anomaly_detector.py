# Brand Protection Monitor, Day 10: statistical anomaly detection
# Implements S10 (price z-score outliers), S11 (listing bursts) and S16 (seller
# behaviour outliers via isolation forest) from docs/signal_spec.csv.
# Rules catch patterns we already know. This layer flags what merely looks abnormal,
# then lets an analyst decide. Signals land in the same table, source 'anomaly'.
# Run from the project root:  python3 src/anomaly_detector.py

import sqlite3
import pandas as pd
from sklearn.ensemble import IsolationForest

AS_OF = "2026-07-07"
con = sqlite3.connect("data/monitor.db")
cur = con.cursor()

# rerunnable: clear previous anomaly signals
cur.execute("DELETE FROM signals WHERE signal_source = 'anomaly'")
written = {}

# ---------------- S10: price z-score outlier within brand ----------------
# How far does each price sit from its brand's average, in standard deviations?
# A caveat every analyst should know: counterfeits themselves drag the mean down,
# so z-scores are a blunt instrument on contaminated data. Day 13 measures how blunt.
prices = pd.read_sql("""
    SELECT l.listing_id, l.price, b.brand_name
    FROM listings l JOIN brands b ON b.brand_id = l.brand_id""", con)
stats = prices.groupby("brand_name")["price"].agg(["mean", "std"])
prices = prices.join(stats, on="brand_name")
prices["z"] = (prices["price"] - prices["mean"]) / prices["std"]
outliers = prices[prices["z"].abs() > 3]
cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'price_zscore_outlier', 'anomaly', ?, 3)",
    [(int(r.listing_id), round(float(r.z), 2)) for r in outliers.itertuples()])
written["price_zscore_outlier"] = len(outliers)

# ---------------- S11: listing burst, many uploads in one day ----------------
bursts = pd.read_sql("""
    SELECT l.listing_id, day_counts.n
    FROM listings l
    JOIN (SELECT seller_id, listed_date, COUNT(*) AS n
          FROM listings GROUP BY seller_id, listed_date
          HAVING COUNT(*) > 5) day_counts
      ON day_counts.seller_id = l.seller_id AND day_counts.listed_date = l.listed_date""", con)
cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'listing_burst', 'anomaly', ?, 3)",
    [(int(r.listing_id), int(r.n)) for r in bursts.itertuples()])
written["listing_burst"] = len(bursts)

# ---------------- S16: seller behaviour outlier, isolation forest ----------------
# Four behavioural features per seller. The forest isolates sellers whose overall
# behaviour is easy to separate from the crowd, no single rule required.
sellers = pd.read_sql(f"""
    SELECT s.seller_id,
           MAX(CAST(julianday('{AS_OF}') - julianday(s.join_date) AS INTEGER), 1) AS age_days,
           COUNT(l.listing_id) AS listings,
           SUM(l.review_count) AS reviews,
           AVG(CASE WHEN b.is_protected = 1 THEN l.price / b.rrp_min END) AS avg_price_ratio
    FROM sellers s
    JOIN listings l ON l.seller_id = s.seller_id
    LEFT JOIN brands b ON b.brand_id = l.brand_id
    GROUP BY s.seller_id""", con)
sellers["listings_per_day"] = sellers["listings"] / sellers["age_days"]
sellers["reviews_per_day"] = sellers["reviews"] / sellers["age_days"]
sellers["avg_price_ratio"] = sellers["avg_price_ratio"].fillna(1.0)

features = sellers[["age_days", "listings_per_day", "reviews_per_day", "avg_price_ratio"]]
forest = IsolationForest(n_estimators=200, contamination=0.15, random_state=42)
sellers["flag"] = forest.fit_predict(features)
sellers["score"] = -forest.score_samples(features)  # higher = more anomalous

flagged_sellers = sellers[sellers["flag"] == -1]
listing_map = pd.read_sql("SELECT listing_id, seller_id FROM listings", con)
hits = listing_map.merge(flagged_sellers[["seller_id", "score"]], on="seller_id")
cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'seller_behaviour_outlier', 'anomaly', ?, 3)",
    [(int(r.listing_id), round(float(r.score), 3)) for r in hits.itertuples()])
written["seller_behaviour_outlier"] = len(hits)
con.commit()

# ---------------- report ----------------
print("ANOMALY DETECTOR RUN")
for k, v in written.items():
    print(f"  {k:<28}{v:>6} signals")
print(f"  {'total':<28}{sum(written.values()):>6}")

names = pd.read_sql("SELECT seller_id, seller_name FROM sellers", con)
top = flagged_sellers.merge(names, on="seller_id").nlargest(8, "score")
print("\nMOST ANOMALOUS SELLERS (isolation forest)")
for r in top.itertuples():
    print(f"  {r.seller_name:<22} score {r.score:.3f}  age {r.age_days}d  "
          f"{r.listings_per_day:.2f} listings/day  price ratio {r.avg_price_ratio:.2f}")

# the payoff question: what did anomalies catch that no rule caught?
new_catches = cur.execute("""
    SELECT COUNT(DISTINCT listing_id) FROM signals
    WHERE signal_source = 'anomaly'
      AND listing_id NOT IN (SELECT listing_id FROM signals WHERE signal_source = 'rule')
""").fetchone()[0]
print(f"\nlistings flagged by anomaly detection that NO rule caught: {new_catches}")
con.close()
