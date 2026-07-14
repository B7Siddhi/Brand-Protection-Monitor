# Brand Protection Monitor, Day 9: rule based detection engine
# Implements signals S01 to S09 from docs/signal_spec.csv.
# Each rule is data: an id, a severity, and a SQL query returning (listing_id, signal_value).
# The engine loops the catalogue, writes every hit to the signals table, and reports.
# Rules stay explainable: every signal row records which rule fired and the measured value.
# Run from the project root:  python3 src/rules_engine.py

import sqlite3

AS_OF = "2026-07-07"  # analysis date for account age calculations

RULES = [
    {"signal_type": "price_below_floor", "severity": 4, "sql": """
        SELECT l.listing_id, ROUND(l.price / b.rrp_min, 3)
        FROM listings l JOIN brands b ON b.brand_id = l.brand_id
        WHERE b.is_protected = 1
          AND l.price / b.rrp_min >= 0.3 AND l.price / b.rrp_min < 0.5"""},

    {"signal_type": "price_extreme", "severity": 5, "sql": """
        SELECT l.listing_id, ROUND(l.price / b.rrp_min, 3)
        FROM listings l JOIN brands b ON b.brand_id = l.brand_id
        WHERE b.is_protected = 1 AND l.price / b.rrp_min < 0.3"""},

    {"signal_type": "young_seller_high_velocity", "severity": 4, "sql": f"""
        WITH sa AS (
            SELECT s.seller_id,
                   MAX(CAST(julianday('{AS_OF}') - julianday(s.join_date) AS INTEGER), 1) AS age_days,
                   COUNT(l.listing_id) AS n
            FROM sellers s JOIN listings l ON l.seller_id = s.seller_id
            GROUP BY s.seller_id)
        SELECT l.listing_id, ROUND(sa.n * 1.0 / sa.age_days, 2)
        FROM listings l JOIN sa ON sa.seller_id = l.seller_id
        WHERE sa.age_days < 60 AND sa.n * 1.0 / sa.age_days > 0.5"""},

    {"signal_type": "unauthorised_protected_seller", "severity": 2, "sql": """
        SELECT l.listing_id, ROUND(l.price / b.rrp_min, 3)
        FROM listings l
        JOIN brands  b ON b.brand_id = l.brand_id
        JOIN sellers s ON s.seller_id = l.seller_id
        WHERE b.is_protected = 1 AND s.is_authorised = 0 AND l.price < b.rrp_min"""},

    {"signal_type": "review_velocity", "severity": 4, "sql": f"""
        WITH rv AS (
            SELECT s.seller_id,
                   SUM(l.review_count) * 1.0 /
                   MAX(CAST(julianday('{AS_OF}') - julianday(s.join_date) AS INTEGER), 1) AS reviews_per_day
            FROM sellers s JOIN listings l ON l.seller_id = s.seller_id
            GROUP BY s.seller_id)
        SELECT l.listing_id, ROUND(rv.reviews_per_day, 2)
        FROM listings l JOIN rv ON rv.seller_id = l.seller_id
        WHERE rv.reviews_per_day > 10"""},

    {"signal_type": "rating_skew", "severity": 3, "sql": """
        SELECT listing_id, avg_rating
        FROM listings
        WHERE avg_rating >= 4.9 AND review_count > 100"""},

    {"signal_type": "shared_image", "severity": 4, "sql": """
        WITH shared AS (
            SELECT image_ref, COUNT(DISTINCT seller_id) AS sellers_sharing
            FROM listings GROUP BY image_ref
            HAVING COUNT(DISTINCT seller_id) > 1)
        SELECT l.listing_id, sh.sellers_sharing
        FROM listings l JOIN shared sh ON sh.image_ref = l.image_ref"""},

    # Tuned on day 9: the first version flagged any description shared by 3+ sellers
    # and hit 1075 listings, because storefront boilerplate spreads across many sellers.
    # Coordinated copying clusters small (3 to 4 sellers); text shared wider than that
    # is treated as boilerplate, not a fraud signal. Day 13 evaluates this formally.
    {"signal_type": "copied_description", "severity": 4, "sql": """
        WITH copied AS (
            SELECT description, COUNT(DISTINCT seller_id) AS sellers_sharing
            FROM listings WHERE description <> ''
            GROUP BY description
            HAVING COUNT(DISTINCT seller_id) BETWEEN 3 AND 4)
        SELECT l.listing_id, c.sellers_sharing
        FROM listings l JOIN copied c ON c.description = l.description"""},

    {"signal_type": "missing_description", "severity": 1, "sql": """
        SELECT listing_id, 1 FROM listings WHERE description = ''"""},
]

con = sqlite3.connect("data/monitor.db")
cur = con.cursor()

# rerunnable: clear previous rule signals before writing fresh ones
cur.execute("DELETE FROM signals WHERE signal_source = 'rule'")

print("RULE ENGINE RUN")
print(f"{'signal_type':<32}{'severity':>9}{'hits':>7}")
print("-" * 48)
total = 0
for rule in RULES:
    hits = cur.execute(rule["sql"]).fetchall()
    cur.executemany(
        "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
        f"VALUES (?, '{rule['signal_type']}', 'rule', ?, {rule['severity']})", hits)
    print(f"{rule['signal_type']:<32}{rule['severity']:>9}{len(hits):>7}")
    total += len(hits)
con.commit()

print("-" * 48)
print(f"{'total signals written':<41}{total:>7}")

# which listings stack the most signals? a preview of day 12 risk scoring
print("\nMOST STACKED LISTINGS (signal count, summed severity)")
for row in cur.execute("""
    SELECT sg.listing_id, s.seller_name, COUNT(*) AS signals, SUM(sg.severity) AS sev_sum
    FROM signals sg
    JOIN listings l ON l.listing_id = sg.listing_id
    JOIN sellers  s ON s.seller_id = l.seller_id
    WHERE sg.signal_source = 'rule'
    GROUP BY sg.listing_id
    ORDER BY sev_sum DESC, signals DESC
    LIMIT 8"""):
    print(f"  listing {row[0]:>5}  {row[1]:<22} signals {row[2]}  severity sum {row[3]}")

flagged = cur.execute(
    "SELECT COUNT(DISTINCT listing_id) FROM signals WHERE signal_source = 'rule'").fetchone()[0]
all_l = cur.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
print(f"\nlistings with at least one signal: {flagged} of {all_l}")
con.close()
