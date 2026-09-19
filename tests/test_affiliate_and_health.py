# ==
# test_affiliate_and_health.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# Same rule as every other test file in this project — recompute the
# real number independently from the source file and check it against
# what the script saved, rather than just checking a column exists.
# Covers the two stages added after the original six: affiliate
# programme analysis (07) and the pipeline health gate (08).

import pandas as pd
import pytest

from conftest import skip_if_missing


# --
# STAGE 7 — AFFILIATE ANALYSIS
# --

def test_affiliate_summary_matches_recomputation(raw_data_dir, outputs_dir):
    affiliates = pd.read_excel(raw_data_dir / "uppromote_affiliates.xlsx")
    saved = pd.read_csv(outputs_dir / "affiliate_summary.csv").iloc[0]

    assert int(saved["total_signups"]) == len(affiliates)
    assert int(saved["active_count"]) == int((affiliates["status"] == "Active").sum())
    assert int(saved["pending_count"]) == int((affiliates["status"] == "Pending").sum())
    assert int(saved["inactive_count"]) == int((affiliates["status"] == "Inactive").sum())
    assert int(saved["verified_count"]) == int((affiliates["verified"] == "yes").sum())
    assert int(saved["never_logged_in_count"]) == int((affiliates["login_count"].fillna(0) == 0).sum())


def test_affiliate_summary_never_claims_order_attribution(outputs_dir):
    """The honesty tripwire for this stage — see DATA_PROVENANCE.md's
    'Known gap'. UpPromote's signup export has no order-reference
    column, so this summary must keep stating that attribution isn't
    available rather than a future edit quietly implying it is.
    """
    saved = pd.read_csv(outputs_dir / "affiliate_summary.csv").iloc[0]
    assert saved["attribution_available"] in (False, "False", 0)
    note = str(saved["attribution_gap_note"]).lower()
    assert "known gap" in note or "no order-reference" in note


def test_affiliate_by_status_totals_match_summary(outputs_dir):
    summary = pd.read_csv(outputs_dir / "affiliate_summary.csv").iloc[0]
    by_status = pd.read_csv(outputs_dir / "affiliate_by_status.csv")
    assert int(by_status["count"].sum()) == int(summary["total_signups"])


# --
# STAGE 8 — PIPELINE HEALTH
# --

def test_pipeline_health_row_counts_match_cleaned_data(cleaned_data_dir, outputs_dir):
    skip_if_missing(cleaned_data_dir / "orders_clean.csv", cleaned_data_dir / "customers_clean.csv")
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    orders = pd.read_csv(cleaned_data_dir / "orders_clean.csv")
    customers = pd.read_csv(cleaned_data_dir / "customers_clean.csv")

    saved = pd.read_csv(outputs_dir / "pipeline_health_summary.csv").iloc[0]
    assert int(saved["products_row_count"]) == len(products)
    assert int(saved["orders_row_count"]) == len(orders)
    assert int(saved["customers_row_count"]) == len(customers)


def test_pipeline_health_reports_healthy_on_a_clean_run(outputs_dir):
    """A regular `python pipeline.py` run against this project's own
    real data should always come back HEALTHY — if this ever fails, a
    real structural problem was introduced upstream and the pipeline
    health check (Stage 10 — 08_pipeline_health.py) caught it, which
    is exactly what it's for. Don't silence this test; fix the
    underlying data problem instead.
    """
    saved = pd.read_csv(outputs_dir / "pipeline_health_summary.csv").iloc[0]
    checks = pd.read_csv(outputs_dir / "pipeline_health_checks.csv")

    assert int(saved["checks_passed"]) == int(saved["checks_total"])
    assert saved["overall_status"] == "HEALTHY"
    assert checks["passed"].all(), (
        f"Failed checks: {checks[~checks['passed']]['check_name'].tolist()}"
    )


def test_pipeline_health_checks_file_is_not_empty(outputs_dir):
    checks = pd.read_csv(outputs_dir / "pipeline_health_checks.csv")
    assert len(checks) > 0
    assert {"check_name", "passed", "detail"}.issubset(checks.columns)
