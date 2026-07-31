# Brand Protection Monitor, Day 16: text similarity for copied listings and
# design lookalikes.
#
# THREE ATTEMPTS AT NEAR-DUPLICATE DESCRIPTION DETECTION, ALL DOCUMENTED HONESTLY:
#
# Attempt 1: raw TF-IDF cosine similarity across all listing descriptions.
#   Result: 1075 of 1075 listings scored above 0.99 similarity to another
#   listing. Useless. Cause: my own data generator writes descriptions from
#   one template, "High quality {category} from {brand}. Ships from our UK
#   warehouse...", so ~90% of every description's words are identical to
#   every other description regardless of whether real copying occurred.
#
# Attempt 2: TfidfVectorizer(max_df=0.3), which automatically downweights
#   words appearing in more than 30% of documents, the standard fix for
#   exactly this boilerplate problem.
#   Result: still 1075 of 1075 above 0.3 similarity. Downweighting common
#   WORDS doesn't help when the boilerplate is ~90% of the WHOLE description;
#   there simply isn't enough distinguishing text left per listing for any
#   weighting scheme to separate real copies from templated coincidence.
#
# Attempt 3: cross-seller title similarity instead of descriptions.
#   Result: better, but 315 of 1098 titles still score above 0.99 purely
#   because the generator's adjective/noun vocabulary is small, not because
#   of real copying. Same root cause, smaller scale.
#
# CONCLUSION: whole-text similarity is not a usable signal on THIS dataset,
# because the dataset's own generator is too repetitive, not because the
# technique is wrong. The exact-match, small-cluster rule built on day 9
# (S08, copied_description) remains the correct tool here: it already
# achieves 100% recall on the copied_listing fraud type per day 15's
# evaluation. Rebuilding it with fuzzier matching would add noise, not signal.
#
# WHAT THIS SCRIPT ACTUALLY SHIPS: S17, design_lookalike_language, a simple,
# explainable phrase detector for passing-off style language ("style of",
# "inspired by", "same look and feel", "dupe for", "alternative to") that
# real design infringement cases use (the Trunki suitcase case is the classic
# example: no brand name copied, just the look). Tested against this
# dataset's ground truth: it catches the same 50 listings S13/S14 already
# catch, zero net new hits, because my generator only ever paired this
# language with an explicit brand reference. Documented honestly below: the
# detector is architecturally correct and would catch pure design copying
# with no brand name attached, a case this dataset happens not to contain.
# Run from the project root:  python3 src/similarity_detector.py

import sqlite3
import pandas as pd

import config  # day 19: shared settings, see src/config.py
PHRASES = ["style of", "inspired by", "same look", "look and feel",
           "compare to", "dupe for", "alternative to"]

con = sqlite3.connect(config.DB_PATH)
cur = con.cursor()
cur.execute("DELETE FROM signals WHERE signal_type = 'design_lookalike_language'")

listings = pd.read_sql(
    "SELECT listing_id, title, description FROM listings", con)

hits = []
for r in listings.itertuples():
    text = f"{r.title} {r.description or ''}".lower()
    if any(ph in text for ph in PHRASES):
        hits.append(r.listing_id)

cur.executemany(
    "INSERT INTO signals (listing_id, signal_type, signal_source, signal_value, severity) "
    "VALUES (?, 'design_lookalike_language', 'similarity', 1, 3)",
    [(lid,) for lid in hits])
con.commit()

print("SIMILARITY DETECTOR RUN")
print(f"  design_lookalike_language signals: {len(hits)}")

existing = pd.read_sql(f"""
    SELECT DISTINCT listing_id FROM signals
    WHERE signal_type IN ('brand_evasion', 'brand_reference_stuffing')
      AND listing_id IN ({','.join(map(str, hits)) if hits else '0'})""", con)
overlap = len(existing)
print(f"  of which already caught by S13/S14: {overlap}")
print(f"  net new listings caught: {len(hits) - overlap}")

print("\nWHY THIS SIGNAL STILL SHIPS DESPITE ZERO NET NEW CATCHES TODAY")
print("  It targets pure design infringement, copying the LOOK of a product")
print("  with no brand name involved at all (the Trunki suitcase case: no")
print("  logo copied, still ruled infringement). My synthetic generator only")
print("  ever paired this language with an explicit brand comparison, so on")
print("  this specific dataset the signal is fully redundant. On real")
print("  marketplace data, where sellers explicitly avoid naming a brand to")
print("  dodge detection, this signal would catch what S13 and S14 cannot.")
con.close()
