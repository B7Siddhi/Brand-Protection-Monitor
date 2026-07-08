# Brand Protection Monitor, Day 5: cleaning and loading pipeline
# Reads raw CSVs from data/raw, validates and standardises them,
# rejects bad rows with a reason, and loads clean data into SQLite.
# Every cleaning decision is logged, because in fraud work you must be able
# to explain why a record was excluded.
# Run from the project root:  python3 src/clean_load.py

import sqlite3
import pandas as pd
from pathlib import Path

RAW = Path("data/raw")
DB = Path("data/monitor.db")
REJECTS = Path("data/rejects_log.csv")

# static demo FX rates for standardising to GBP
FX_TO_GBP = {"GBP": 1.0, "USD": 0.78, "EUR": 0.85}

report = {}
rejects = []

def reject(df_rows, reason):
    for _, r in df_rows.iterrows():
        rejects.append({"listing_id": r.get("listing_id"), "reason": reason})

# ---------------- load raw files ----------------
listings = pd.read_csv(RAW / "listings_raw.csv")
sellers = pd.read_csv(RAW / "sellers_raw.csv")
reviews = pd.read_csv(RAW / "reviews_raw.csv")
brands = pd.read_csv(RAW / "brands.csv")
report["raw listings"] = len(listings)

# ---------------- step 1: remove duplicate rows ----------------
before = len(listings)
listings = listings.drop_duplicates(subset="listing_id", keep="first")
report["duplicates removed"] = before - len(listings)

# ---------------- step 2: standardise brand names ----------------
# raw data contains NIKE, nike and Nike; map case insensitively to the brand list
brand_lookup = {b.lower(): b for b in brands["brand_name"]}
needs_fix = int((~listings["brand"].isin(brands["brand_name"])).sum())
listings["brand"] = listings["brand"].str.strip().str.lower().map(brand_lookup)
unknown = listings[listings["brand"].isna()]
reject(unknown, "unknown brand")
listings = listings.dropna(subset=["brand"])
report["brand case fixes applied"] = needs_fix - len(unknown)

# ---------------- step 3: standardise currency to GBP ----------------
listings["currency"] = listings["currency"].str.strip().str.upper()
bad_ccy = listings[~listings["currency"].isin(FX_TO_GBP)]
reject(bad_ccy, "unrecognised currency")
listings = listings[listings["currency"].isin(FX_TO_GBP)]
converted = int((listings["currency"] != "GBP").sum())
listings["price"] = (listings["price"] * listings["currency"].map(FX_TO_GBP)).round(2)
listings["currency"] = "GBP"
report["prices converted to GBP"] = converted

# ---------------- step 4: reject impossible prices ----------------
bad_price = listings[listings["price"] <= 0]
reject(bad_price, "non positive price")
listings = listings[listings["price"] > 0]
report["impossible prices rejected"] = len(bad_price)

# ---------------- step 5: referential integrity ----------------
# every listing must point at a seller we know
orphans = listings[~listings["seller_id"].isin(sellers["seller_id"])]
reject(orphans, "seller not found")
listings = listings[listings["seller_id"].isin(sellers["seller_id"])]
report["orphan listings rejected"] = len(orphans)

# ---------------- step 6: flag, do not reject, missing descriptions ----------------
missing_desc = int(listings["description"].isna().sum() + (listings["description"] == "").sum())
listings["description"] = listings["description"].fillna("")
report["missing descriptions flagged"] = missing_desc

# reviews: keep only reviews for listings that survived cleaning
before = len(reviews)
reviews = reviews.drop_duplicates(subset="review_id")
reviews = reviews[reviews["listing_id"].isin(listings["listing_id"])]
report["reviews dropped (orphaned or duplicate)"] = before - len(reviews)

report["clean listings loaded"] = len(listings)
report["rows rejected total"] = len(rejects)

# ---------------- load into SQLite ----------------
con = sqlite3.connect(DB)
cur = con.cursor()

# rebuild tables from the schema so the pipeline is rerunnable end to end
for t in ["alerts", "signals", "reviews", "listings", "brands", "sellers"]:
    cur.execute(f"DROP TABLE IF EXISTS {t}")
cur.executescript(Path("src/schema.sql").read_text())

# reviews table, schema v2: added today because review text arrives with the raw data
cur.executescript("""
CREATE TABLE reviews (
    review_id    INTEGER PRIMARY KEY,
    listing_id   INTEGER NOT NULL REFERENCES listings(listing_id),
    rating       INTEGER CHECK (rating BETWEEN 1 AND 5),
    review_text  TEXT,
    review_date  DATE
);
CREATE INDEX idx_reviews_listing ON reviews(listing_id);
""")

brands = brands.reset_index(drop=True)
brands["brand_id"] = brands.index + 1
brands[["brand_id", "brand_name", "is_protected", "rrp_min", "rrp_max"]].to_sql("brands", con, if_exists="append", index=False)

sellers.to_sql("sellers", con, if_exists="append", index=False)

brand_ids = dict(zip(brands["brand_name"], brands["brand_id"]))
listings = listings.assign(brand_id=listings["brand"].map(brand_ids)).drop(columns=["brand"])
listings.to_sql("listings", con, if_exists="append", index=False)

reviews.to_sql("reviews", con, if_exists="append", index=False)
con.commit()

# ---------------- rejects log and quality report ----------------
pd.DataFrame(rejects).to_csv(REJECTS, index=False)

print("DATA QUALITY REPORT")
for k, v in report.items():
    print(f"  {k}: {v}")
print(f"rejects log written to {REJECTS}")

# quick verification queries
for q, label in [
    ("SELECT COUNT(*) FROM listings", "listings in database"),
    ("SELECT COUNT(*) FROM sellers", "sellers in database"),
    ("SELECT COUNT(*) FROM reviews", "reviews in database"),
    ("SELECT COUNT(*) FROM listings WHERE price <= 0", "impossible prices remaining (should be 0)"),
]:
    print(f"  {label}: {cur.execute(q).fetchone()[0]}")
con.close()
