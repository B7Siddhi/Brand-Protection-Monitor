# Brand Protection Monitor, Day 6: exploratory fraud analysis
# Five analytical SQL queries against the clean database, each one a documented finding.
# Concepts used: joins, GROUP BY with HAVING, CTEs, window functions, date arithmetic.
# Run from the project root:  python3 src/explore.py

import sqlite3
import pandas as pd

pd.set_option("display.width", 120)
con = sqlite3.connect("data/monitor.db")

def finding(n, title, insight, sql):
    print(f"\n{'=' * 78}")
    print(f"FINDING {n}: {title}")
    print(insight)
    print("-" * 78)
    print(pd.read_sql(sql, con).to_string(index=False))

# ---------------------------------------------------------------- 1
finding(1, "Sellers pricing far below the genuine floor",
"Protected brands have a known retail range. Sellers whose average price sits\n"
"under half the genuine minimum are the classic counterfeit profile.",
"""
SELECT s.seller_name,
       COUNT(*)                                   AS listings,
       ROUND(AVG(l.price), 2)                     AS avg_price,
       ROUND(AVG(l.price / b.rrp_min), 2)         AS avg_price_vs_floor
FROM listings l
JOIN brands  b ON b.brand_id = l.brand_id
JOIN sellers s ON s.seller_id = l.seller_id
WHERE b.is_protected = 1
GROUP BY s.seller_id
HAVING AVG(l.price / b.rrp_min) < 0.5
ORDER BY avg_price_vs_floor
LIMIT 10;
""")

# ---------------------------------------------------------------- 2
finding(2, "Young accounts listing at high velocity",
"A CTE computes each seller's account age and listing count. Established shops\n"
"grow slowly; fraud accounts arrive and flood the marketplace within days.",
"""
WITH seller_activity AS (
    SELECT s.seller_id, s.seller_name,
           CAST(julianday('2026-07-07') - julianday(s.join_date) AS INTEGER) AS account_age_days,
           COUNT(l.listing_id) AS listings
    FROM sellers s
    JOIN listings l ON l.seller_id = s.seller_id
    GROUP BY s.seller_id
)
SELECT seller_name, account_age_days, listings,
       ROUND(listings * 1.0 / MAX(account_age_days, 1), 2) AS listings_per_day
FROM seller_activity
WHERE account_age_days < 60
ORDER BY listings_per_day DESC
LIMIT 10;
""")

# ---------------------------------------------------------------- 3
finding(3, "Review counts that defy time",
"Reviews accumulate over months. A seller whose listings hold hundreds of\n"
"reviews after days of existence is buying them.",
"""
SELECT s.seller_name,
       CAST(julianday('2026-07-07') - julianday(s.join_date) AS INTEGER) AS account_age_days,
       SUM(l.review_count)  AS total_reviews,
       ROUND(AVG(l.avg_rating), 2) AS avg_rating
FROM sellers s
JOIN listings l ON l.seller_id = s.seller_id
GROUP BY s.seller_id
HAVING total_reviews > 500 AND account_age_days < 90
ORDER BY total_reviews DESC;
""")

# ---------------------------------------------------------------- 4
finding(4, "One photo, many sellers",
"Legitimate sellers photograph their own stock. The same image reference\n"
"appearing across several unrelated sellers marks a counterfeit supply ring.",
"""
SELECT l.image_ref,
       COUNT(DISTINCT l.seller_id) AS sellers_sharing,
       COUNT(*)                    AS listings,
       ROUND(AVG(l.price), 2)      AS avg_price
FROM listings l
GROUP BY l.image_ref
HAVING COUNT(DISTINCT l.seller_id) > 1
ORDER BY sellers_sharing DESC
LIMIT 8;
""")

# ---------------------------------------------------------------- 5
finding(5, "Copied listings, ranked with a window function",
"RANK() orders each seller's listings by price inside one query. Applied to\n"
"sellers sharing an identical description, it exposes a coordinated network\n"
"undercutting genuine retail together.",
"""
WITH copied AS (
    SELECT description
    FROM listings
    WHERE description <> ''
    GROUP BY description
    HAVING COUNT(DISTINCT seller_id) >= 3
)
SELECT s.seller_name, b.brand_name, l.price,
       RANK() OVER (PARTITION BY l.seller_id ORDER BY l.price) AS price_rank_within_seller
FROM listings l
JOIN copied  c ON c.description = l.description
JOIN sellers s ON s.seller_id = l.seller_id
JOIN brands  b ON b.brand_id = l.brand_id
ORDER BY s.seller_name, price_rank_within_seller
LIMIT 12;
""")

print(f"\n{'=' * 78}")
print("Five findings documented. Next step: turn these patterns into automated")
print("detection rules (day 9) so no analyst has to run them by hand.")
con.close()
