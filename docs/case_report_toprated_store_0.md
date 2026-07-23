# Case Report: Seller toprated_store_0 (ID 73)

**Prepared by:** Siddhi Bhalerao
**Date:** Day 14 of Brand Protection Monitor build, July 2026
**Classification:** Internal investigation output, synthetic data, portfolio project
**Case rank:** #1 of 26 alerted sellers, by average risk score

## Summary

Seller toprated_store_0 is an 11 day old, unauthorised account carrying 10 listings across six protected brands, all priced within plausible retail range. Every listing scored the maximum composite risk score of 22.1, the highest in the dataset, driven by three independent detectors agreeing on every single listing: abnormal listing velocity for the account's age, review velocity that is not achievable through organic purchase activity, and template review text repeated across listings. The pattern is consistent with review fraud used to manufacture trust rather than counterfeit pricing, and the seller's activity should be considered high priority for review suspension pending manual verification.

## Seller profile

| Field | Value |
|---|---|
| Seller ID | 73 |
| Account age | 11 days (joined 2026-06-26) |
| Country | GB |
| Authorised reseller status | No |
| Total listings | 10 |
| Total alerts raised | 10 (100 percent of listings) |
| Marketplace baseline for comparison | 29.0 average reviews per listing, 4.08 average rating |

## Evidence

### 1. Listing velocity inconsistent with organic growth

The account posted 10 listings within an 11 day window, a rate of 0.91 listings per day. Established legitimate sellers in this dataset average well under this rate over months of activity. This alone raised the `young_seller_high_velocity` signal (severity 4) on all 10 listings.

### 2. Review velocity that cannot occur through genuine purchase activity

Combined listings carry review counts as high as 595 on a single item, accumulated within days of the account's existence. This computes to 378.91 reviews per day of account life, a figure that is not achievable through organic customer purchase and review behaviour under any realistic conversion assumption. This raised `review_velocity` (severity 4) on all 10 listings, the same signal weight as the velocity finding above, and together these two signals form the backbone of the case.

### 3. Rating saturation

Every listing carries a rating of 4.9 or 5.0, against a marketplace baseline of 4.08. Combined with volume this far exceeds what organic review distributions produce; genuine review populations include a meaningful share of 3 and 4 star reviews even for well regarded sellers. This raised `rating_skew` (severity 3).

### 4. Duplicate review text

Text similarity analysis (day 11) found review text repeated 4 to 7 times per listing at a similarity threshold of 0.9 or above, consistent with a small set of template reviews posted repeatedly rather than organic independent customer writing. This raised `duplicate_review_text` (severity 3) on all 10 listings.

### 5. Behavioural outlier confirmation

Independent of any rule, the isolation forest model (day 10) isolated this seller as a behavioural outlier with an anomaly score of 0.764, the second highest in the dataset, using only account age, listing velocity, review velocity and price ratio as inputs, no review text or rule logic involved. This is a fifth, methodologically independent line of evidence pointing at the same seller.

### Convergence

All five signals above come from three separate detectors: rule engine, isolation forest, and TF-IDF text similarity. No single detector alone would justify escalation at this confidence level; the case is built on agreement across independently designed methods measuring different aspects of the same account.

## Listings under review

| Listing | Brand | Price (GBP) | Listed | Reviews | Rating |
|---|---|---|---|---|---|
| 1045 | Generic | 35.96 | 2026-06-05 | 551 | 4.9 |
| 1047 | Louis Vuitton | 564.70 | 2026-06-05 | 213 | 4.9 |
| 1049 | Charlotte Tilbury | 73.67 | 2026-06-11 | 179 | 4.9 |
| 1043 | Adidas | 120.12 | 2026-06-14 | 567 | 4.9 |
| 1044 | Gucci | 1,560.94 | 2026-06-22 | 443 | 5.0 |
| 1046 | Nike | 114.35 | 2026-06-22 | 550 | 4.9 |
| 1050 | Adidas | 105.55 | 2026-06-22 | 588 | 5.0 |
| 1048 | Gucci | 557.77 | 2026-06-23 | 260 | 5.0 |
| 1041 | Charlotte Tilbury | 66.03 | 2026-06-26 | 222 | 5.0 |
| 1042 | Charlotte Tilbury | 47.84 | 2026-06-26 | 595 | 5.0 |

Note: unlike the counterfeit typology documented on day 2, none of these listings are priced below the genuine retail floor. This case is not counterfeit pricing; it is review manipulation used to fast track trust and search ranking on otherwise plausibly priced listings, a distinct typology from the price-anomaly cases that dominate the rest of the alert queue.

## Timeline

The seller's first two listings appear on 2026-06-05. Activity is sparse for the following six days, then accelerates sharply: five listings post between 2026-06-22 and 2026-06-23, and two more on 2026-06-26, the account's most recent activity as of this analysis. Review counts on the earliest listings already exceed 500 within days of posting, indicating review accumulation began at or near listing creation rather than building organically over the account's short life.

## Typology classification

Per the typology matrix (`docs/typology_matrix.csv`), this case is classified as **review and rating fraud**, a product fraud enabler rather than a standalone counterfeit or IP infringement case. Its function is to manufacture the trust signals (volume, rating) that make fraudulent or otherwise low quality listings appear credible to buyers and to marketplace ranking algorithms.

## Recommended action

1. Suspend new listing privileges for this seller pending manual review.
2. Refer review history for the seller's 10 listings to platform trust and safety for authenticity audit, prioritising the four listings posted 2026-06-22 to 2026-06-23 where review accumulation is most concentrated.
3. Cross check whether any linked accounts share review text templates with this seller (see `src/case_extract.py` for the linked seller query used to check shared images across accounts; no shared image ring was found for this seller specifically, so any connected accounts would need to be identified via review text matching rather than image matching).
4. No brand rights holder notification required at this stage: no evidence of counterfeit pricing or trademark misuse was found in this specific case, and any brand escalation should await the trust and safety audit outcome.

## Evidence trail reproducibility

Every figure in this report can be reproduced by running `src/case_extract.py` against `data/monitor.db` after the detection pipeline (`src/rules_engine.py`, `src/anomaly_detector.py`, `src/review_signals.py`, `src/risk_scorer.py`) has been run in sequence. No figure in this report was manually calculated or estimated.
