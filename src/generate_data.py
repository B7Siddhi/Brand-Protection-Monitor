# Brand Protection Monitor, Day 4: synthetic data generator
# Generates realistic marketplace listings with fraud patterns deliberately planted,
# plus a ground truth file so detection can be measured honestly on day 13.
# Synthetic data was chosen over scraping live marketplaces: no terms of service risk,
# and known ground truth makes precision measurable.
# Run from the project root:  python3 src/generate_data.py
# Output lands in data/raw/ which is gitignored; this script is the reproducible source.

import csv
import os
import random
from datetime import date, timedelta

random.seed(42)  # fixed seed so every run produces identical data

TODAY = date(2026, 7, 7)
OUT = "data/raw"
os.makedirs(OUT, exist_ok=True)

# ---------------- brands ----------------
# name, protected flag, genuine retail price range
BRANDS = [
    ("Nike", 1, 60, 180), ("Adidas", 1, 55, 170), ("Louis Vuitton", 1, 400, 3500),
    ("Gucci", 1, 350, 3000), ("Rolex", 1, 4000, 25000), ("Apple", 1, 120, 1400),
    ("Samsung", 1, 100, 1300), ("Dyson", 1, 250, 700), ("Lego", 1, 15, 350),
    ("The North Face", 1, 80, 400), ("Charlotte Tilbury", 1, 25, 95), ("Generic", 0, 5, 60),
]

CATEGORIES = ["Trainers", "Handbags", "Watches", "Electronics", "Home", "Toys", "Outdoor", "Beauty", "Clothing"]
COUNTRIES = ["GB", "GB", "GB", "US", "DE", "CN", "HK", "TR", "FR", "IN"]
EVASIONS = {"Nike": ["N1ke", "Nlke", "NIK3"], "Gucci": ["Guccl", "GUC-CI", "Gucc1"],
            "Rolex": ["Ro1ex", "RLX luxury"], "Louis Vuitton": ["LV style", "Louls Vuitton"],
            "Apple": ["App1e", "A-pple"]}

ADJ = ["Genuine", "Brand New", "Authentic", "Premium", "Classic", "Limited Edition", "2026", "Original", "Boxed"]
NOUN = {"Trainers": ["Air Runner", "Street Pro", "Court Classic"], "Handbags": ["Tote", "Crossbody", "Clutch"],
        "Watches": ["Chronograph", "Diver", "Dress Watch"], "Electronics": ["Wireless Earbuds", "Smartwatch", "Tablet"],
        "Home": ["Cordless Vacuum", "Air Purifier", "Fan"], "Toys": ["Building Set", "Starter Kit", "Playset"],
        "Outdoor": ["Puffer Jacket", "Fleece", "Backpack"], "Beauty": ["Lipstick Set", "Skincare Kit", "Palette"],
        "Clothing": ["Hoodie", "Track Jacket", "T Shirt"]}

TEMPLATE_REVIEWS = [
    "Amazing product fast shipping five stars would buy again",
    "Best purchase ever highly recommend this seller great quality",
    "Perfect item exactly as described very happy top seller",
]
REAL_REVIEWS = [
    "Decent quality for the price, delivery took a week", "Happy with it overall, box was slightly damaged",
    "Works as expected", "Good value, would recommend", "Not bad, sizing runs a little small",
    "Great product, second time ordering", "Arrived quickly, well packaged", "Does the job",
]

sellers, listings, reviews, truth = [], [], [], []
sid, lid, rid = 0, 0, 0

def add_seller(name, days_old, country, authorised):
    global sid
    sid += 1
    sellers.append({"seller_id": sid, "seller_name": name, "join_date": (TODAY - timedelta(days=days_old)).isoformat(),
                    "country": country, "is_authorised": authorised})
    return sid

def add_listing(seller, brand, title, desc, cat, price, listed_days_ago, rc, rating, image):
    global lid
    lid += 1
    listings.append({"listing_id": lid, "seller_id": seller, "brand": brand, "title": title,
                     "description": desc, "category": cat, "price": price, "currency": "GBP",
                     "listed_date": (TODAY - timedelta(days=listed_days_ago)).isoformat(),
                     "review_count": rc, "avg_rating": rating, "image_ref": image})
    return lid

def add_reviews(listing, n, fake=False):
    global rid
    for _ in range(n):
        rid += 1
        text = random.choice(TEMPLATE_REVIEWS) if fake else random.choice(REAL_REVIEWS)
        rating = 5 if fake else random.choice([2, 3, 3, 4, 4, 4, 5, 5])
        reviews.append({"review_id": rid, "listing_id": listing, "rating": rating, "review_text": text,
                        "review_date": (TODAY - timedelta(days=random.randint(0, 60))).isoformat()})

def title_for(brand, cat):
    return f"{random.choice(ADJ)} {brand} {random.choice(NOUN[cat])}"

def desc_for(brand, cat):
    return (f"High quality {cat.lower()} from {brand}. Ships from our UK warehouse within 2 days. "
            f"All items checked before dispatch. Contact us with any questions.")

# ---------------- 60 legitimate sellers, about 900 listings ----------------
for i in range(60):
    s = add_seller(f"seller_{i:03d}", random.randint(200, 3000), random.choice(COUNTRIES), random.random() < 0.3)
    for _ in range(random.randint(8, 20)):
        b_name, prot, lo, hi = random.choice(BRANDS)
        cat = random.choice(CATEGORIES)
        price = round(random.uniform(lo, hi), 2)
        n_rev = random.randint(0, 40)
        l = add_listing(s, b_name, title_for(b_name, cat), desc_for(b_name, cat), cat, price,
                        random.randint(1, 300), n_rev, round(random.uniform(3.4, 4.8), 1) if n_rev else "",
                        f"img_{random.randint(10000, 99999)}")
        add_reviews(l, min(n_rev, 5))

# ---------------- pattern 1: counterfeiters, 8 young sellers, deep discounts, shared images ----------------
shared_images = [f"img_fake_{n}" for n in range(6)]
for i in range(8):
    s = add_seller(f"dealz_direct_{i}", random.randint(5, 45), random.choice(["CN", "HK", "TR"]), 0)
    for _ in range(random.randint(15, 30)):
        b_name, prot, lo, hi = random.choice([b for b in BRANDS if b[1] == 1])
        cat = random.choice(CATEGORIES)
        price = round(lo * random.uniform(0.15, 0.45), 2)  # 55 to 85 percent below the genuine floor
        l = add_listing(s, b_name, title_for(b_name, cat), desc_for(b_name, cat), cat, price,
                        random.randint(1, 30), random.randint(0, 8), round(random.uniform(3.0, 4.5), 1),
                        random.choice(shared_images))
        truth.append({"listing_id": l, "fraud_type": "counterfeit"})

# ---------------- pattern 2: brand evasion, 4 sellers with disguised brand names ----------------
for i in range(4):
    s = add_seller(f"bargain_hub_{i}", random.randint(30, 200), random.choice(COUNTRIES), 0)
    for _ in range(random.randint(10, 18)):
        real = random.choice(list(EVASIONS))
        b_lo = next(b[2] for b in BRANDS if b[0] == real)
        cat = random.choice(CATEGORIES)
        evaded = random.choice(EVASIONS[real])
        l = add_listing(s, "Generic", f"{random.choice(ADJ)} {evaded} style {random.choice(NOUN[cat])}",
                        f"Compare to {real}. Same look and feel at a fraction of the price. Fast UK shipping.",
                        cat, round(b_lo * random.uniform(0.2, 0.5), 2), random.randint(1, 90),
                        random.randint(0, 15), round(random.uniform(3.5, 4.6), 1), f"img_{random.randint(10000, 99999)}")
        truth.append({"listing_id": l, "fraud_type": "brand_evasion"})

# ---------------- pattern 3: review fraud, 4 sellers with impossible review velocity ----------------
for i in range(4):
    s = add_seller(f"toprated_store_{i}", random.randint(10, 60), random.choice(COUNTRIES), 0)
    for _ in range(random.randint(6, 12)):
        b_name, prot, lo, hi = random.choice(BRANDS)
        cat = random.choice(CATEGORIES)
        l = add_listing(s, b_name, title_for(b_name, cat), desc_for(b_name, cat), cat,
                        round(random.uniform(lo, hi) * 0.8, 2), random.randint(1, 40),
                        random.randint(150, 600), round(random.uniform(4.9, 5.0), 1),
                        f"img_{random.randint(10000, 99999)}")
        add_reviews(l, 12, fake=True)
        truth.append({"listing_id": l, "fraud_type": "review_fraud"})

# ---------------- pattern 4: copied listings, 4 linked sellers sharing one description word for word ----------------
copied_desc = ("Luxury designer quality guaranteed 100 percent authentic comes with dust bag and receipt "
               "ships same day from London warehouse no returns accepted final sale")
for i in range(4):
    s = add_seller(f"luxe_outlet_{i}", random.randint(15, 90), "GB", 0)
    for _ in range(random.randint(5, 10)):
        b_name, prot, lo, hi = random.choice([("Louis Vuitton", 1, 400, 3500), ("Gucci", 1, 350, 3000)])
        cat = random.choice(["Handbags", "Clothing"])
        l = add_listing(s, b_name, title_for(b_name, cat), copied_desc, cat,
                        round(lo * random.uniform(0.25, 0.6), 2), random.randint(1, 60),
                        random.randint(0, 10), round(random.uniform(4.0, 4.8), 1), "img_luxe_001")
        truth.append({"listing_id": l, "fraud_type": "copied_listing"})

# ---------------- realistic mess for day 5 cleaning ----------------
for row in random.sample(listings, 30):
    listings.append(dict(row))                      # exact duplicate rows
for row in random.sample(listings, 25):
    row["description"] = ""                          # missing descriptions
for row in random.sample(listings, 15):
    row["country_note"] = ""
    row["currency"] = random.choice(["USD", "EUR", "gbp"])  # inconsistent currencies
for row in random.sample(listings, 8):
    row["price"] = -abs(float(row["price"]))         # impossible negative prices
for row in random.sample(listings, 20):
    row["brand"] = row["brand"].upper() if random.random() < 0.5 else row["brand"].lower()  # case chaos

# ---------------- write files ----------------
def write(name, rows, fields):
    with open(f"{OUT}/{name}", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

write("sellers_raw.csv", sellers, ["seller_id", "seller_name", "join_date", "country", "is_authorised"])
write("listings_raw.csv", listings, ["listing_id", "seller_id", "brand", "title", "description", "category",
                                     "price", "currency", "listed_date", "review_count", "avg_rating", "image_ref"])
write("reviews_raw.csv", reviews, ["review_id", "listing_id", "rating", "review_text", "review_date"])
write("brands.csv", [{"brand_name": b[0], "is_protected": b[1], "rrp_min": b[2], "rrp_max": b[3]} for b in BRANDS],
      ["brand_name", "is_protected", "rrp_min", "rrp_max"])
write("ground_truth.csv", truth, ["listing_id", "fraud_type"])

print(f"sellers:  {len(sellers)}")
print(f"listings: {len(listings)} (including {len(truth)} planted fraud listings and 30 duplicate rows)")
print(f"reviews:  {len(reviews)}")
print("fraud planted:", {t: sum(1 for x in truth if x['fraud_type'] == t) for t in set(x['fraud_type'] for x in truth)})
print("files written to data/raw/")
