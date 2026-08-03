# Brand Protection Monitor

An end to end pipeline that detects product fraud and IP infringement in marketplace listings: it ingests listing data, screens it for counterfeit and infringement signals, scores risk, and surfaces ranked alerts for investigators.

**Live demo:** [brand-protection-monitor-s7b.streamlit.app](https://brand-protection-monitor-s7b.streamlit.app/), the investigator dashboard, live, no setup required.

Built in public over 21 days. Follow the journey on [LinkedIn](https://www.linkedin.com/in/siddhi-bhalerao7).

## Why

Global trade in counterfeit goods reached 467 billion dollars in 2021, around 2.3 percent of world imports (OECD and EUIPO, Mapping Global Trade in Fakes 2025). Most of it now moves through online marketplaces one listing at a time. Finding those listings among millions of legitimate ones is a data problem, and this project is a working answer to it.

## Architecture
```
generate_data.py --> clean_load.py --> four detectors --> risk_scorer.py --> dashboard/app.py
raw listings validate, rules, anomaly, composite Streamlit
(fraud planted, standardise, review NLP, risk score, investigator
ground truth kept) reject w/reason trademark fuzzy banded alerts dashboard
load to SQLite match, network graph
|
v
monitor.db
sellers | brands | listings | reviews | signals | alerts
```

Rule engine, anomaly detection (isolation forest), review fraud NLP, trademark fuzzy matching, seller network analysis, composite risk scoring, and the Streamlit dashboard are all built and live. Measured against ground truth: 96.4% precision, 100% recall across every fraud type in the dataset (`src/evaluate.py`).

Shared thresholds and settings (risk bands, the fuzzy match cutoff, the analysis date) live in one place, `src/config.py`, instead of being duplicated across detectors. `src/run_pipeline.py` runs every stage in order behind a single command, with logging to `logs/pipeline.log` and a fail-fast stop on the first broken step.

## What it detects

Product fraud: counterfeit listings, seller impersonation, review and rating fraud, grey market activity.

IP infringement: trademark misuse and brand keyword evasion, copied listings, design lookalikes, linked repeat infringer networks.

The full mapping of each fraud type to its detectable signals is in `docs/typology_matrix.csv` and `docs/signal_spec.csv`.

## Data

The pipeline runs on synthetic marketplace data generated with a fixed random seed, so every run is reproducible. Fraud patterns are deliberately planted and recorded in a ground truth file, which makes detection measurable: precision and recall get computed against known answers, the same way real fraud teams validate against confirmed historical cases. No live marketplaces were scraped.

## Setup

```
git clone https://github.com/B7Siddhi/Brand-Protection-Monitor.git
cd Brand-Protection-Monitor
pip install -r requirements.txt
```

## Running it

```
python3 src/run_pipeline.py # runs every stage in order, one command, logs to logs/pipeline.log
streamlit run dashboard/app.py # investigator dashboard
```

Or run each stage by hand, useful when developing a single detector:

```
python3 src/generate_data.py # create raw data in data/raw
python3 src/clean_load.py # clean, log rejects, load monitor.db
python3 src/rules_engine.py # rule based signals
python3 src/anomaly_detector.py # isolation forest + statistical signals
python3 src/review_signals.py # review fraud NLP
python3 src/trademark_detector.py # fuzzy brand evasion matching
python3 src/similarity_detector.py # design lookalike language
python3 src/risk_scorer.py # composite score, writes alerts
python3 src/evaluate.py # precision/recall against ground truth
python3 src/network_analysis.py # seller network clusters
```

The dashboard bootstraps its own database automatically on first run if one doesn't exist yet, so `streamlit run dashboard/app.py` alone is enough for a fresh clone.

## Tests

```
pip install pytest
python3 -m pytest tests/ -v
```

Six tests: four fast unit tests (config sanity, schema structure, the fuzzy match threshold, risk band boundaries), plus two integration tests that run the real scripts, one against a small hand built fixture to check row level cleaning decisions, one running the full pipeline end to end and checking it still hits 100% recall.

## Regulatory context

This project is built on more than pattern matching. Its design choices, a risk-based composite score instead of a single hard rule, a convergence bonus for independent signals agreeing, precision and recall measured against labelled ground truth before anything is trusted, come directly from AML and financial crime risk management practice (the ICA and ACAMS syllabuses), and map onto where a tool like this would actually sit in an organisation's three lines model. The review fraud detector (S12) is a direct, working answer to a live legal requirement: the UK's Digital Markets, Competition and Consumers Act 2024 requires platforms to take reasonable steps to detect and remove fake reviews. Full writeup, including the UK legal framework behind each fraud type detected and the enforcement bodies involved, in `docs/regulatory_context.md`.

## Repository layout

```
src/ pipeline code, schema and every detector
docs/ project scope, typology matrix, signal spec, data dictionary, case report, regulatory context
data/ database and rejects log (raw data is generated, not committed)
dashboard/ Streamlit investigator dashboard
tests/ automated tests, unit and integration
```

## Findings so far

Five documented exploratory findings, nine rule based signals, statistical and NLP based detectors, and a full investigation case report on the highest risk seller found (`docs/case_report_toprated_store_0.md`). Run `src/explore.py` to reproduce the exploratory findings, or open the live dashboard to browse alerts directly.

## Author

Siddhi Bhalerao. Fraud investigation background, building in public toward marketplace risk and brand protection work.


