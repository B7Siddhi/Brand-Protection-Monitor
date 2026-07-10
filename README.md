# Brand Protection Monitor

An end to end pipeline that detects product fraud and IP infringement in marketplace listings: it ingests listing data, screens it for counterfeit and infringement signals, scores risk, and surfaces ranked alerts for investigators.

Built in public over 21 days. Follow the journey on [LinkedIn]([www.linkedin.com/in/siddhi-bhalerao7](https://www.linkedin.com/in/siddhi-bhalerao7).

## Why

Global trade in counterfeit goods reached 467 billion dollars in 2021, around 2.3 percent of world imports (OECD and EUIPO, Mapping Global Trade in Fakes 2025). Most of it now moves through online marketplaces one listing at a time. Finding those listings among millions of legitimate ones is a data problem, and this project is a working answer to it.

## Architecture

```
generate_data.py          clean_load.py               explore.py
raw listings CSVs   -->   validate, standardise,  -->  analytical SQL
(fraud planted,           reject with reasons,         findings
 ground truth kept)       load to SQLite
                          |
                          v
                     monitor.db
        sellers | brands | listings | reviews | signals | alerts
```

Coming in weeks 2 and 3: rule engine, anomaly detection, review fraud signals, trademark fuzzy matching, copied listing detection, seller network analysis, composite risk scoring, and a Streamlit investigator dashboard.

## What it detects

Product fraud: counterfeit listings, seller impersonation, review and rating fraud, grey market activity.

IP infringement: trademark misuse and brand keyword evasion, copied listings, design lookalikes, linked repeat infringer networks.

The full mapping of each fraud type to its detectable signals is in `docs/typology_matrix.csv`.

## Data

The pipeline runs on synthetic marketplace data generated with a fixed random seed, so every run is reproducible. Fraud patterns are deliberately planted and recorded in a ground truth file, which makes detection measurable: precision and recall get computed against known answers, the same way real fraud teams validate against confirmed historical cases. No live marketplaces were scraped.

## Running it

Requires Python 3 and pandas.

```
python3 src/generate_data.py   # create raw data in data/raw
python3 src/clean_load.py      # clean, log rejects, load monitor.db
python3 src/explore.py         # print five documented findings
```

## Repository layout

```
src/        pipeline code and schema
docs/       project scope, typology matrix, data dictionary
data/       database and rejects log (raw data is generated, not committed)
dashboard/  investigator dashboard (week 3)
```

## Findings so far

Five documented findings from exploratory analysis, including sellers averaging 25 percent of genuine retail price, a seller account 11 days old carrying over 4000 five star reviews, and one product photo shared by 8 unrelated sellers. Run `src/explore.py` to reproduce them.

## Author

Siddhi Bhalerao. Fraud investigation background, building in public toward marketplace risk and brand protection work.
