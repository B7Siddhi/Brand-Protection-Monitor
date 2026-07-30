# Brand Protection Monitor, Day 18: investigator dashboard
# A screen an investigator can actually work from, instead of reading
# seventeen days of Terminal output. Three views: an alert queue they can
# filter and sort, trend charts showing where risk concentrates, and a
# seller drill down showing the full evidence trail behind any one alert,
# the same evidence a case report (day 14) would be built from.
# Run from the project root:  streamlit run dashboard/app.py

import sqlite3
import subprocess
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Brand Protection Monitor", layout="wide")

DB_PATH = "data/monitor.db"

# The database is intentionally not committed to GitHub, it is generated
# data, not source. On a fresh deployment (e.g. Streamlit Community Cloud)
# there is no database yet, so the full pipeline runs once, automatically,
# to build one. Locally, if you already ran the pipeline yourself, this
# does nothing, since the file already exists.
def ensure_pipeline_has_run():
    if Path(DB_PATH).exists():
        return
    steps = ["generate_data.py", "clean_load.py", "rules_engine.py",
              "anomaly_detector.py", "review_signals.py", "trademark_detector.py",
              "similarity_detector.py", "risk_scorer.py"]
    with st.spinner("First run detected: building the detection pipeline from scratch, "
                     "this takes about 20 seconds..."):
        for step in steps:
            result = subprocess.run(["python3", f"src/{step}"], capture_output=True, text=True)
            if result.returncode != 0:
                st.error(f"Pipeline step {step} failed:\n{result.stderr}")
                st.stop()

ensure_pipeline_has_run()

@st.cache_data(ttl=60)
def load_data():
    con = sqlite3.connect(DB_PATH)
    alerts = pd.read_sql("""
        SELECT a.alert_id, a.listing_id, a.seller_id, s.seller_name, a.risk_score,
               a.risk_band, a.status, l.title, l.price, b.brand_name, l.listed_date
        FROM alerts a
        JOIN listings l ON l.listing_id = a.listing_id
        JOIN sellers  s ON s.seller_id = a.seller_id
        LEFT JOIN brands b ON b.brand_id = l.brand_id""", con)
    signals = pd.read_sql("""
        SELECT listing_id, signal_type, signal_source, signal_value, severity
        FROM signals""", con)
    sellers = pd.read_sql("SELECT * FROM sellers", con)
    con.close()
    return alerts, signals, sellers

try:
    alerts, signals, sellers = load_data()
except Exception as e:
    st.error(f"Could not load data/monitor.db: {e}. "
             f"Run the pipeline scripts in src/ first, in order, from the project root.")
    st.stop()

if alerts.empty:
    st.warning("No alerts found. Run src/rules_engine.py through src/risk_scorer.py first.")
    st.stop()

st.title("Brand Protection Monitor")
st.caption("Product fraud and IP infringement detection, alert queue and investigation view")

# ---------------- KPI row ----------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total alerts", len(alerts))
k2.metric("High risk", int((alerts["risk_band"] == "high").sum()))
k3.metric("Medium risk", int((alerts["risk_band"] == "medium").sum()))
k4.metric("Sellers implicated", alerts["seller_id"].nunique())

st.divider()

tab_queue, tab_trends, tab_seller = st.tabs(
    ["Alert queue", "Trends", "Seller drill down"])

# ---------------- Alert queue ----------------
with tab_queue:
    st.subheader("Alert queue")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        band_filter = st.multiselect("Risk band", ["high", "medium", "low"],
                                      default=["high", "medium"])
    with col_f2:
        sources = sorted(signals["signal_source"].unique())
        source_filter = st.multiselect("Signal source", sources, default=sources)
    with col_f3:
        min_score = st.slider("Minimum risk score", 0.0, float(alerts["risk_score"].max()), 0.0)

    relevant_listings = signals[signals["signal_source"].isin(source_filter)]["listing_id"].unique()
    filtered = alerts[
        alerts["risk_band"].isin(band_filter)
        & alerts["risk_score"].ge(min_score)
        & alerts["listing_id"].isin(relevant_listings)
    ].sort_values("risk_score", ascending=False)

    st.write(f"{len(filtered)} alerts match the current filters")
    st.dataframe(
        filtered[["listing_id", "seller_name", "brand_name", "title", "price",
                  "risk_score", "risk_band", "status"]],
        width="stretch", hide_index=True, height=420)

# ---------------- Trends ----------------
with tab_trends:
    st.subheader("Where risk concentrates")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Alerts by risk band**")
        st.bar_chart(alerts["risk_band"].value_counts())
    with c2:
        st.markdown("**Signals fired, by type**")
        st.bar_chart(signals["signal_type"].value_counts())

    st.markdown("**Top 10 sellers by average alert score**")
    leaderboard = (alerts.groupby("seller_name")["risk_score"]
                    .agg(["mean", "count"]).round(1)
                    .rename(columns={"mean": "avg_risk_score", "count": "alerts"})
                    .sort_values("avg_risk_score", ascending=False).head(10))
    st.bar_chart(leaderboard["avg_risk_score"])
    st.dataframe(leaderboard, width="stretch")

# ---------------- Seller drill down ----------------
with tab_seller:
    st.subheader("Investigate a seller")
    seller_options = alerts.sort_values("risk_score", ascending=False)["seller_name"].unique()
    chosen = st.selectbox("Select a seller, highest risk first", seller_options)

    seller_row = sellers[sellers["seller_name"] == chosen].iloc[0]
    sid = int(seller_row["seller_id"])
    account_age_days = (pd.Timestamp("2026-07-07") - pd.to_datetime(seller_row["join_date"])).days

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Account age (days)", account_age_days, help=f"Joined {seller_row['join_date']}")
    c2.metric("Country", seller_row.get("country", "n/a"))
    c3.metric("Authorised reseller", "Yes" if seller_row.get("is_authorised") else "No")
    seller_alerts = alerts[alerts["seller_id"] == sid]
    c4.metric("Alerts on this seller", len(seller_alerts))

    st.markdown("**Listings and alerts**")
    st.dataframe(
        seller_alerts[["listing_id", "title", "brand_name", "price", "risk_score", "risk_band"]]
        .sort_values("risk_score", ascending=False),
        width="stretch", hide_index=True)

    st.markdown("**Full evidence trail**")
    seller_listing_ids = seller_alerts["listing_id"].tolist()
    evidence = signals[signals["listing_id"].isin(seller_listing_ids)].sort_values(
        "severity", ascending=False)
    st.dataframe(
        evidence[["listing_id", "signal_type", "signal_source", "signal_value", "severity"]],
        width="stretch", hide_index=True)

    st.caption("This is the same evidence a case report (docs/case_report_*.md) is built from, "
               "here browsable instead of hand pulled with case_extract.py.")

st.divider()
st.caption("Brand Protection Monitor, day 18 of 21. Data refreshes from data/monitor.db "
           "each time the detection pipeline is rerun.")
