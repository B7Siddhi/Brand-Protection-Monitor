# Brand Protection Monitor, Day 12: composite risk scoring
# Collapses every signal from every detector into one risk score per listing,
# bands the scores, and writes alerts for the medium and high bands.
#
# Scoring design, kept deliberately explainable:
#   score  = sum of severities of the distinct signal types on the listing
#   bonus  = convergence multiplier when independent detectors agree
#            (x1.0 one source, x1.15 two sources, x1.3 three or more)
#   bands  = high at 12 and above, medium at 6 to 11.99, low below 6
#   alerts = medium and high only; low stays logged but does not page a human
# Every threshold is a choice an analyst can defend, and day 13 will test them.
# Run from the project root:  python3 src/risk_scorer.py

import sqlite3
import pandas as pd

HIGH, MEDIUM = 12, 6
BONUS = {1: 1.0, 2: 1.15}   # 3+ sources handled below

con = sqlite3.connect("data/monitor.db")
cur = con.cursor()

signals = pd.read_sql("""
    SELECT listing_id, signal_type, signal_source, MAX(severity) AS severity
    FROM signals
    GROUP BY listing_id, signal_type, signal_source""", con)
if signals.empty:
    raise SystemExit("no signals found; run the detectors first")

per_listing = signals.groupby("listing_id").agg(
    base=("severity", "sum"),
    types=("signal_type", "nunique"),
    sources=("signal_source", "nunique")).reset_index()
per_listing["score"] = (per_listing["base"] *
    per_listing["sources"].map(lambda s: BONUS.get(s, 1.3))).round(2)
per_listing["band"] = pd.cut(per_listing["score"],
    bins=[0, MEDIUM, HIGH, float("inf")],
    labels=["low", "medium", "high"], right=False)

sellers = pd.read_sql("SELECT listing_id, seller_id FROM listings", con)
per_listing = per_listing.merge(sellers, on="listing_id")

# rerunnable: rebuild alerts from scratch
cur.execute("DELETE FROM alerts")
alertable = per_listing[per_listing["band"].isin(["medium", "high"])]
cur.executemany(
    "INSERT INTO alerts (listing_id, seller_id, risk_score, risk_band) VALUES (?, ?, ?, ?)",
    [(int(r.listing_id), int(r.seller_id), float(r.score), str(r.band))
     for r in alertable.itertuples()])
con.commit()

print("RISK SCORER RUN")
total = pd.read_sql("SELECT COUNT(*) n FROM listings", con)["n"][0]
print(f"  listings total:      {total}")
print(f"  listings with score: {len(per_listing)}")
for band in ["high", "medium", "low"]:
    n = (per_listing["band"] == band).sum()
    print(f"  band {band:<7} {n:>5}")
print(f"  alerts written:      {len(alertable)}  (medium and high only)")

print("\nTOP 10 ALERTS")
top = pd.read_sql("""
    SELECT a.listing_id, s.seller_name, a.risk_score, a.risk_band
    FROM alerts a JOIN sellers s ON s.seller_id = a.seller_id
    ORDER BY a.risk_score DESC LIMIT 10""", con)
for r in top.itertuples():
    print(f"  listing {r.listing_id:>5}  {r.seller_name:<22} score {r.risk_score:>6}  {r.risk_band}")

# explainability demo: the full evidence trail behind the number one alert
top_id = int(top.iloc[0]["listing_id"])
print(f"\nWHY IS LISTING {top_id} THE TOP ALERT?")
for row in cur.execute("""
    SELECT signal_type, signal_source, signal_value, severity
    FROM signals WHERE listing_id = ? ORDER BY severity DESC""", (top_id,)):
    print(f"  [{row[1]:<7}] {row[0]:<28} value {row[2]:>8}  severity {row[3]}")

print("\nSELLER RISK LEADERBOARD (average alert score, alert count)")
for row in cur.execute("""
    SELECT s.seller_name, ROUND(AVG(a.risk_score), 1), COUNT(*)
    FROM alerts a JOIN sellers s ON s.seller_id = a.seller_id
    GROUP BY a.seller_id ORDER BY AVG(a.risk_score) DESC LIMIT 8"""):
    print(f"  {row[0]:<24} avg score {row[1]:>6}  alerts {row[2]}")
con.close()
