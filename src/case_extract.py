# Brand Protection Monitor, Day 14: case investigation data pull
# Pulls every fact needed to write a full case report on the single highest
# risk seller: profile, every listing, every signal with its value, and how
# this seller compares to the marketplace baseline.
# Run from the project root:  python3 src/case_extract.py

import sqlite3
import pandas as pd

con = sqlite3.connect("data/monitor.db")

top_seller_id = pd.read_sql("""
    SELECT seller_id FROM alerts
    GROUP BY seller_id ORDER BY AVG(risk_score) DESC LIMIT 1""", con).iloc[0, 0]

profile = pd.read_sql(f"""
    SELECT seller_name, join_date, country, is_authorised,
           CAST(julianday('2026-07-07') - julianday(join_date) AS INTEGER) AS age_days
    FROM sellers WHERE seller_id = {top_seller_id}""", con).iloc[0]

listings = pd.read_sql(f"""
    SELECT l.listing_id, l.title, b.brand_name, l.price, b.rrp_min, b.rrp_max,
           l.listed_date, l.review_count, l.avg_rating, l.image_ref
    FROM listings l LEFT JOIN brands b ON b.brand_id = l.brand_id
    WHERE l.seller_id = {top_seller_id} ORDER BY l.listed_date""", con)

signals = pd.read_sql(f"""
    SELECT sg.listing_id, sg.signal_type, sg.signal_source, sg.signal_value, sg.severity
    FROM signals sg JOIN listings l ON l.listing_id = sg.listing_id
    WHERE l.seller_id = {top_seller_id}
    ORDER BY sg.severity DESC""", con)

alerts = pd.read_sql(f"""
    SELECT listing_id, risk_score, risk_band FROM alerts
    WHERE seller_id = {top_seller_id} ORDER BY risk_score DESC""", con)

baseline = pd.read_sql("""
    SELECT AVG(review_count) avg_reviews, AVG(avg_rating) avg_rating
    FROM listings WHERE avg_rating IS NOT NULL""", con).iloc[0]

market_rank = pd.read_sql("""
    SELECT seller_id, AVG(risk_score) s FROM alerts GROUP BY seller_id
    ORDER BY s DESC""", con)
rank = int(market_rank[market_rank["seller_id"] == top_seller_id].index[0]) + 1
total_sellers_with_alerts = len(market_rank)

print(f"SELLER: {profile['seller_name']}  (id {top_seller_id})")
print(f"  rank: #{rank} of {total_sellers_with_alerts} sellers with alerts, by average risk score")
print(f"  joined: {profile['join_date']}  ({profile['age_days']} days old as of analysis date)")
print(f"  country: {profile['country']}   authorised reseller: {'yes' if profile['is_authorised'] else 'no'}")
print(f"  total listings: {len(listings)}   total alerts: {len(alerts)}")
print(f"  marketplace baseline: avg {baseline['avg_reviews']:.1f} reviews, avg {baseline['avg_rating']:.2f} rating")

print(f"\nLISTINGS ({len(listings)})")
for r in listings.itertuples():
    flag = "GENUINE FLOOR" if pd.notna(r.rrp_min) and r.price < r.rrp_min * 0.5 else ""
    print(f"  #{r.listing_id} {r.brand_name or 'Generic':<12} {r.title[:40]:<40} "
          f"GBP{r.price:>9,.2f}  listed {r.listed_date}  reviews {r.review_count:>4}  "
          f"rating {r.avg_rating}  {flag}")

print(f"\nALL SIGNALS FIRED ({len(signals)}), highest severity first")
for r in signals.itertuples():
    print(f"  listing #{r.listing_id:<6} [{r.signal_source:<7}] {r.signal_type:<28} "
          f"value {r.signal_value:>8}  severity {r.severity}")

print(f"\nALERTS ({len(alerts)})")
for r in alerts.itertuples():
    print(f"  listing #{r.listing_id:<6} score {r.risk_score:>6}  {r.risk_band}")

# shared image ring: who else uses this seller's images?
if not listings.empty:
    refs = "','".join(listings["image_ref"].dropna().unique())
    ring = pd.read_sql(f"""
        SELECT DISTINCT s.seller_name FROM listings l JOIN sellers s ON s.seller_id = l.seller_id
        WHERE l.image_ref IN ('{refs}') AND l.seller_id != {top_seller_id}""", con)
    if len(ring):
        print(f"\nLINKED SELLERS (share at least one image with this seller): {', '.join(ring['seller_name'])}")

con.close()
