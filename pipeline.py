# ==
# pipeline.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# Same reasoning as Project 1's runner — running each analysis script
# by hand is easy to get out of order, and it's easy to forget a
# stage and look at outputs based on stale data without noticing.
# This has grown the same way Project 1's did, one stage at a time,
# and now runs all ten of Project 2's own stages in order.
#
# HOW TO RUN:
#   python pipeline.py
#
# ABOUT THE LOGGING:
# This used to just print everything straight to the terminal. It now
# goes through Python's logging module instead, at INFO/WARNING/ERROR
# levels, and every run also writes a plain-text copy to
# pipeline_run.log in the project root (overwritten each run, not
# accumulated, and it's gitignored since it's a local run artifact,
# not project data). That means a failed run can be diffed or grepped
# afterwards, and it's a step toward this being pluggable into real
# monitoring later, instead of only ever being read by a person
# watching the terminal at the moment it runs.
#
# STAGE ORDER MATTERS:
# Stage 2 depends on Stage 1 having written products_clean.csv.
# Stages 3-6 each depend on Stage 1's cleaned data and/or an earlier
# stage's own output (04 reads Stage 3's funnel_summary.csv; 06 reads
# it too). Stage 7 is independent — it reads the raw UpPromote export
# directly, not any cleaned/output file. The catalogue-vs-sales-mix
# check also depends only on Stage 1's cleaned data plus the raw order
# export — it compares real catalogue mix against real sales mix, no
# simulated data. The external-category-benchmark check (Stage 9)
# depends on the catalogue-vs-sales-mix output (Stage 8) plus the real
# external Olist dataset in raw_data/external_olist/ — it compares
# Seamark's real sales mix against that external dataset's real order
# mix, still no simulated data on either side. 08_pipeline_health.py
# runs LAST on purpose (even though its filename number is lower than
# the other two) because it re-checks the outputs every earlier stage
# just wrote, so it needs all of them to already exist. The run order
# below is what actually controls execution order, not the filename
# numbers.
# ==

import logging
import os
import subprocess
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ANALYTICS_DIR = os.path.join(PROJECT_ROOT, "analytics")
LOG_FILE = os.path.join(PROJECT_ROOT, "pipeline_run.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("pipeline")

START_TIME = datetime.now()

log.info("=" * 62)
log.info("  SEAMARK GLOBAL INNOVATIONS")
log.info("  Post-Launch Data Science Pipeline (Project 2)")
log.info(f"  Started: {START_TIME.strftime('%d %B %Y at %H:%M:%S')}")
log.info("=" * 62)


pipeline_stages = [
    ("01_data_cleaning.py",          "Stage 1 — Data Cleaning (Products, Orders, Customers)"),
    ("02_product_classification.py", "Stage 2 — Product Classification, Country Breakdown & Text Clustering (TF-IDF/K-Means)"),
    ("03_funnel_analysis.py",        "Stage 3 — Funnel Analysis, Bot Traffic Adjustment & Drop-off Scenario"),
    ("04_forecast_vs_actual.py",     "Stage 4 — Forecast Accuracy Check & Capital-Exposure Estimate"),
    ("05_pricing_integrity.py",      "Stage 5 — Pricing Integrity Check & Margin Anomaly Detection"),
    ("06_omnichannel_visibility.py",  "Stage 6 — Omnichannel Visibility (Shopify + Google Merchant Center)"),
    ("07_affiliate_analysis.py",      "Stage 7 — Affiliate Programme Analysis (UpPromote signups)"),
    ("09_catalog_vs_sales_mix.py",    "Stage 8 — Catalogue Mix vs Real Sales Mix (by category)"),
    ("10_external_category_benchmark.py", "Stage 9 — Real Sales Mix vs External (Olist) Real Order Mix"),
    ("08_pipeline_health.py",         "Stage 10 — Pipeline Health Check (launch-readiness gate, runs last)"),
]

results = []

for filename, stage_name in pipeline_stages:

    log.info("─" * 62)
    log.info(f"  {stage_name}")
    log.info(f"  Running: {filename}")
    log.info("─" * 62)

    try:
        result = subprocess.run(
            [sys.executable, filename],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=ANALYTICS_DIR,
        )

        if result.returncode == 0:
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    log.info(f"  {line}")
            log.info("  Result: SUCCESS")
            results.append((stage_name, "SUCCESS", None))

        else:
            error_snippet = result.stderr[-300:] if result.stderr else "No error output captured"
            log.error("  Result: FAILED")
            log.error(f"  Error : {error_snippet}")
            if result.stderr and "ModuleNotFoundError" in result.stderr:
                missing_module = result.stderr.strip().split('\n')[-1].split("'")
                missing_module = missing_module[1] if len(missing_module) > 1 else "a required package"
                log.warning(f"  Fix   : '{missing_module}' isn't installed in this Python environment.")
                log.warning("          Run this from the project root, then try again: pip install -r requirements.txt")
            results.append((stage_name, "FAILED", error_snippet))

    except subprocess.TimeoutExpired:
        log.error("  Result: TIMEOUT — exceeded 120 seconds")
        results.append((stage_name, "TIMEOUT", "Exceeded 120 second limit"))

    except Exception as e:
        log.error(f"  Result: ERROR — {str(e)}")
        results.append((stage_name, "ERROR", str(e)))


END_TIME = datetime.now()
DURATION = (END_TIME - START_TIME).seconds

success_count = sum(1 for _, status, _ in results if status == "SUCCESS")
fail_count = len(results) - success_count

log.info("=" * 62)
log.info("  PIPELINE SUMMARY")
log.info("=" * 62)

for stage_name, status, error in results:
    status_label = "OK  " if status == "SUCCESS" else "FAIL"
    line_log = log.info if status == "SUCCESS" else log.error
    line_log(f"  [{status_label}]  {stage_name}")
    if error:
        line_log(f"         {error[:120]}")

log.info("─" * 62)
log.info(f"  Stages run    : {len(pipeline_stages)}")
log.info(f"  Successful    : {success_count}")
log.info(f"  Failed        : {fail_count}")
log.info(f"  Duration      : {DURATION} seconds")
log.info(f"  Finished      : {END_TIME.strftime('%d %B %Y at %H:%M:%S')}")
log.info("─" * 62)

if fail_count == 0:
    log.info("  ALL STAGES PASSED")
    log.info("  Cleaned data  : cleaned_data/")
    log.info("  CSV/chart out : outputs/")
    log.info("  Affiliate signups are analysed (Stage 7); real order-level affiliate")
    log.info("  attribution and live-rate integration still depend on data this store")
    log.info("  doesn't have yet — see DATA_PROVENANCE.md's 'Known gap' section.")
else:
    log.error(f"  PIPELINE FINISHED WITH {fail_count} FAILURE(S)")
    log.warning("  Common causes:")
    log.warning("  - Missing CSV in raw_data/")
    log.warning("  - Column name changed in latest Shopify export")
    log.warning("  - Run the failed stage individually to see the full error")

log.info("=" * 62)
