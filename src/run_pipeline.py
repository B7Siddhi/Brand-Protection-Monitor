# Brand Protection Monitor, Day 19: end to end orchestration
# One command that runs the whole detection pipeline in order, ingestion
# through to a dashboard-ready database, with proper logging instead of
# eighteen days of scattered print statements, and error handling that
# stops cleanly at the first broken step instead of leaving a half built
# database behind.
# Run from the project root:  python3 src/run_pipeline.py

import logging
import subprocess
import sys
import time
from pathlib import Path

import config

# Every pipeline step, in the order data actually has to flow: generate raw
# data, clean and load it, then each detector, then the composite score.
# evaluate.py and network_analysis.py are reporting steps, not required for
# the dashboard, but run.py logs them too so one command gives the full
# picture, same as running everything by hand used to.
STEPS = [
    "generate_data.py",
    "clean_load.py",
    "rules_engine.py",
    "anomaly_detector.py",
    "review_signals.py",
    "trademark_detector.py",
    "similarity_detector.py",
    "risk_scorer.py",
    "evaluate.py",
    "network_analysis.py",
]

Path("logs").mkdir(exist_ok=True)

# Two log destinations at once: the terminal, for watching it run live, and
# a file, for looking back at a run later without having scrolled back far
# enough in the terminal. This is the standard pattern for a script that
# needs to be both watchable now and auditable later.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log"),
    ],
)
log = logging.getLogger("pipeline")


def run_step(script):
    """Run one pipeline script as a subprocess, return (success, seconds)."""
    log.info(f"START  {script}")
    start = time.time()
    # sys.executable, not "python3": the lesson day 18 taught the hard way,
    # deploying to Streamlit Cloud. "python3" can resolve to a different
    # interpreter than the one running this script, and only this one has
    # requirements.txt's packages installed.
    result = subprocess.run(
        [sys.executable, f"src/{script}"], capture_output=True, text=True)
    elapsed = time.time() - start

    if result.returncode != 0:
        log.error(f"FAILED {script} after {elapsed:.1f}s")
        # log the real error, not a vague "something went wrong": the last
        # 20 lines of stderr are almost always where the actual traceback is
        for line in result.stderr.strip().splitlines()[-20:]:
            log.error(f"    {line}")
        return False, elapsed

    log.info(f"OK     {script} ({elapsed:.1f}s)")
    return True, elapsed


def main():
    log.info("PIPELINE RUN STARTING")
    log.info(f"  {len(STEPS)} steps queued, database target: {config.DB_PATH}")

    total_start = time.time()
    for script in STEPS:
        success, _ = run_step(script)
        if not success:
            # stop immediately: every later step reads data this one was
            # supposed to write, so continuing past a failure just produces
            # more confusing failures downstream, not useful partial results
            log.error(f"PIPELINE STOPPED at {script}. See logs/pipeline.log for full output.")
            sys.exit(1)

    total = time.time() - total_start
    log.info(f"PIPELINE COMPLETE in {total:.1f}s, database ready at {config.DB_PATH}")


if __name__ == "__main__":
    main()
