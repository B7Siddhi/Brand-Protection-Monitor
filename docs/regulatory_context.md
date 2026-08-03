# Regulatory context

Why this pipeline exists, who would actually use it, and which frameworks and laws its design choices answer to. Written day 20, after the detection layer was already built, as a deliberate exercise: work backwards from a finished system to the governance model and legal framework it would need to sit inside at a real company.

## Where this sits in the three lines model

The Institute of Internal Auditors' Three Lines Model (updated in 2020 from the older "Three Lines of Defence" name, to shift the framing from purely defensive to value-protecting and value-creating) splits risk ownership three ways:

- **First line**: the people who own and manage risk day to day. In a marketplace trust and safety function, that's the analysts working the alert queue, closing cases, and deciding whether a flagged listing gets removed.
- **Second line**: the function that sets policy, builds the tools, and monitors whether the first line's controls are actually working. This is where this project lives. Deciding that a fuzzy match score of 75 (not 85) separates real brand evasion from noise, or that a risk score needs three converging signals rather than one to justify escalation, is a second line risk judgement, not a first line operational one.
- **Third line**: independent assurance, normally internal audit, checking that the first and second lines are doing what they claim.

`risk_scorer.py` and `evaluate.py` are the clearest second line pieces of this codebase: they don't investigate any individual case, they calibrate and then prove the calibration of the control that the first line will use. Precision and recall, tracked in `evaluate.py`, are the second line's ongoing evidence that the control is fit for purpose, the same evidence a risk function would present at a governance committee.

## Concepts this project borrows from AML and financial crime practice

The ICA Diploma in Anti-Money Laundering and ACAMS's CAMS syllabus both center on a small set of ideas that turn out to transfer directly to product fraud and IP infringement, even though neither syllabus is written with marketplaces in mind:

**Risk-based approach.** Neither body teaches a single fixed rule for flagging a customer or transaction. They teach weighting indicators and setting thresholds that a risk owner can defend, then revisiting them as evidence comes in. `risk_scorer.py`'s composite score (sum of severities, multiplied by a convergence bonus) is exactly that: a defensible, tunable weighting, not a hardcoded cutoff nobody could explain in a review.

**Convergence of red flags.** Standard AML doctrine treats a single red flag as weak evidence and several independent red flags on the same subject as strong evidence, because unrelated indicators agreeing is much harder to happen by chance than any one indicator alone. The convergence bonus in this project (1.0x for one signal source, 1.15x for two, 1.3x for three or more) formalises that exact reasoning for product fraud instead of money laundering.

**Customer due diligence, adapted.** A seller's `join_date`, `is_authorised` flag, and `country` are a lightweight equivalent of a KYC profile. S03 (`young_seller_high_velocity`, an account under 60 days old listing unusually fast) is structurally the same red flag AML analysts are trained to spot: a new relationship moving volume immediately after onboarding, before there is any track record to justify it.

**Testing and back-testing before anything goes live.** Both syllabuses require that a monitoring model be evaluated against known outcomes, not shipped on judgement alone. `evaluate.py` against `ground_truth.csv` (day 13) is that discipline: 96.4% precision and 100% recall are not claims, they are measurements against labelled data, the same way a transaction monitoring model would be back-tested against historical confirmed cases before deployment.

**Case management and escalation.** The `alerts` table's `risk_band` (low, medium, high) and `status` (new, in_review, escalated, closed) columns mirror a standard fraud or AML case management workflow: not every flag needs a human, but every flag that does gets a lifecycle, not just a boolean.

## UK legal framework behind each fraud type detected

| Fraud type detected | Relevant UK law | Enforcement body |
|---|---|---|
| Counterfeit listings, brand evasion (S01, S02, S13) | Trade Marks Act 1994 | UK Intellectual Property Office (IPO), National Trading Standards, and the multi-agency National Markets Group for IP Protection, which includes the Anti-Counterfeiting Group |
| Copied listings, design lookalikes (S08, S17) | Trade Marks Act 1994; passing off | IPO, National Trading Standards |
| Fake and purchased reviews, rating manipulation (S06, S12) | Digital Markets, Competition and Consumers Act 2024, consumer protection provisions in force since 6 April 2025 | Competition and Markets Authority (CMA) |
| Misleading pricing on unauthorised or grey market stock (S01, S04) | Consumer Protection from Unfair Trading Regulations 2008 | Trading Standards |
| General fraud reporting route for affected consumers | n/a | Action Fraud, the UK's national fraud and cybercrime reporting centre |

The review fraud detector (S12, `duplicate_review_text`) is the most directly regulation-relevant piece of this codebase right now. The DMCC Act 2024 requires platforms hosting reviews to take "reasonable and proportionate steps" to prevent, detect, and remove fake reviews, and gives the CMA power to enforce that duty. It does not define what "reasonable and proportionate" means in code. A TF-IDF similarity detector flagging listings with three or more near-duplicate reviews is a concrete, defensible answer to that question, not the only possible one, but a real one, tested against labelled data.

## Where this would sit in a real organisation

A production version of this pipeline would not be owned by a single analyst indefinitely. Second line risk or compliance would own the scoring logic and threshold calibration (this project's `config.py` and `risk_scorer.py`), review precision and recall on a scheduled basis, and adjust thresholds when either metric drifts. First line trust and safety analysts would own the alert queue itself, the `dashboard/app.py` view, investigating and closing individual cases. Internal audit (third line) would periodically sample closed cases and re-run `evaluate.py`-style checks independently, to confirm the second line's own reported numbers hold up.

The synthetic dataset and fixed-seed generator (`generate_data.py`) exist specifically so this entire evaluation loop is reproducible and auditable: anyone can rerun `src/run_pipeline.py` from a clean clone and get the same 305 alerts, the same 96.4% precision, the same 100% recall, every time. That reproducibility is itself a governance property, not just a testing convenience.
