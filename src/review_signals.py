# Brand Protection Monitor, Day 11: review fraud signals
# Implements S12 duplicate_review_text from docs/signal_spec.csv using TF-IDF
# vectors and cosine similarity, the first NLP in the pipeline.
# The idea: review farms paste templates. Vectorise each listing's reviews,
# measure pairwise similarity, and flag listings where 3 or more reviews are
# near copies of each other. Also prints a rating distribution analysis,
# because skewed distributions are the other review fraud tell.
# Run from the project root:  python3 src/review_signals.py

import sqlite3
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SIMILARITY = 0.9   # reviews this alike are treated as the same template
MIN_COPIES = 3     # spec S12: 3 or more near duplicates on one listing

con = sqlite3.connect("data/monitor.db")
cur = con.cursor()
cur.execute("DELETE FROM signals WHERE signal_source = 'review'")

reviews = pd.read_sql(
    "SELECT listing_id, review_text FROM reviews WHERE review_text <> ''", con)

hits = []
for listing_id, grp in reviews.groupby("listing_id"):
    texts = grp["review_text"].tolist()
    if len(texts) < MIN_COPIES:
        continue
    # TF-IDF turns each review into a weighted word vector;
    # cosine similarity of 1.0 means identical wording
    vectors = TfidfVectorizer().fit_transform(texts)
    sim = cosine_similarity(vectors)
    # for each review, count how many OTHER reviews are near copies of it
    near_copies = (sim >= SIMILARITY).sum(axis=1) - 1
    largest_group = int(near_copies.max()) + 1
    if (near_copies >= MIN_COPIES - 1).sum() >= MIN_COPIES:
        hits.append((int(listing_id), largest_group))

cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'duplicate_review_text', 'review', ?, 3)", hits)
con.commit()

print("REVIEW SIGNAL RUN")
print(f"  listings screened:             {reviews['listing_id'].nunique()}")
print(f"  duplicate_review_text signals: {len(hits)}")

# whose listings carry template reviews?
print("\nSELLERS WITH TEMPLATE REVIEWS")
for row in cur.execute("""
    SELECT s.seller_name, COUNT(*) AS flagged_listings, MAX(sg.signal_value) AS biggest_group
    FROM signals sg
    JOIN listings l ON l.listing_id = sg.listing_id
    JOIN sellers  s ON s.seller_id = l.seller_id
    WHERE sg.signal_type = 'duplicate_review_text'
    GROUP BY s.seller_id ORDER BY flagged_listings DESC LIMIT 8"""):
    print(f"  {row[0]:<24} flagged listings {row[1]:>3}   largest template group {int(row[2])}")

# rating distribution analysis: fraud reviews skew hard to 5 stars
print("\nRATING DISTRIBUTION, flagged vs unflagged listings")
dist = pd.read_sql("""
    SELECT r.rating,
           SUM(CASE WHEN f.listing_id IS NOT NULL THEN 1 ELSE 0 END) AS flagged,
           SUM(CASE WHEN f.listing_id IS NULL THEN 1 ELSE 0 END) AS unflagged
    FROM reviews r
    LEFT JOIN (SELECT DISTINCT listing_id FROM signals
               WHERE signal_type = 'duplicate_review_text') f
      ON f.listing_id = r.listing_id
    GROUP BY r.rating ORDER BY r.rating""", con)
for r in dist.itertuples():
    f_pct = 100 * r.flagged / max(dist["flagged"].sum(), 1)
    u_pct = 100 * r.unflagged / max(dist["unflagged"].sum(), 1)
    print(f"  {r.rating} stars   flagged {f_pct:5.1f}%   unflagged {u_pct:5.1f}%")

example = cur.execute("""
    SELECT r.review_text, COUNT(*) FROM reviews r
    JOIN signals sg ON sg.listing_id = r.listing_id
    WHERE sg.signal_type = 'duplicate_review_text'
    GROUP BY r.review_text ORDER BY COUNT(*) DESC LIMIT 1""").fetchone()
if example:
    print(f"\nmost repeated review text ({example[1]} occurrences):")
    print(f'  "{example[0]}"')
con.close()
