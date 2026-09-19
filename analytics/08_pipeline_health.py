# ==
# 08_pipeline_health.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY THIS EXISTS:
# Every stage above this one answers a business question. This one
# answers a different question: did the pipeline itself run cleanly
# enough to be trusted? "All 6 stages printed SUCCESS" (pipeline.py's
# own summary) only means each script exited 0 — it doesn't check that
# the outputs those scripts wrote are actually internally consistent
# with each other. This stage re-checks the same handful of structural
# invariants the test suite checks (no duplicate product handles, every
# output file present and non-empty, the headline counts agreeing with
# each other), but from inside the pipeline run itself, and writes the
# result to a file — so a dashboard or API can show "is this data
# trustworthy right now" without shelling out to pytest.
#
# WHAT THIS IS NOT:
# Not a replacement for the test suite in tests/ — those tests
# recompute each number independently from raw data and are the real
# correctness check, run with `pytest` in CI or before a release. This
# is a lighter, always-on version of a handful of the same checks,
# meant to run as part of every normal `python pipeline.py`.
# ==

import sys
from pathlib import Path

import pandas as pd

OUTPUTS_DIR = Path('../outputs')
CLEANED_DATA_DIR = Path('../cleaned_data')

checks = []


def check(name, passed, detail=""):
    # Column is named 'check_name', not 'check' — CHECK is a reserved SQL
    # keyword and would need quoting everywhere it's used once this lands
    # in Supabase (see supabase/schema.sql's pipeline_health_checks table).
    checks.append({'check_name': name, 'passed': bool(passed), 'detail': detail})
    status = 'OK  ' if passed else 'FAIL'
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


print("=== PIPELINE HEALTH CHECK ===")

expected_outputs = [
    'category_by_country.csv', 'category_vs_cluster.csv', 'cluster_top_terms.csv',
    'catalog_vs_sales_mix.csv', 'external_category_benchmark.csv',
    'forecast_vs_actual_summary.csv', 'funnel_summary.csv',
    'margin_anomaly_check.csv', 'omnichannel_visibility_summary.csv',
    'pricing_integrity_check.csv', 'pricing_integrity_summary.csv',
]
print("\nOutput files:")
for filename in expected_outputs:
    path = OUTPUTS_DIR / filename
    exists = path.exists()
    non_empty = exists and path.stat().st_size > 0
    check(f"outputs/{filename} exists and is non-empty", exists and non_empty)

print("\nStructural invariants:")
products = pd.read_csv(CLEANED_DATA_DIR / 'products_clean.csv')
check(
    "products_clean.csv has no duplicate Handle values",
    products['Handle'].duplicated().sum() == 0,
    f"{products['Handle'].duplicated().sum()} duplicates found" if products['Handle'].duplicated().sum() else "",
)
check(
    "Every product has an Auto_Category",
    products['Auto_Category'].notna().all(),
)
check(
    "Every product has a Text_Cluster assignment",
    products['Text_Cluster'].notna().all(),
)

orders = pd.read_csv(CLEANED_DATA_DIR / 'orders_clean.csv')
customers = pd.read_csv(CLEANED_DATA_DIR / 'customers_clean.csv')
orders_total = round(orders['Total'].sum(), 2)
customers_total = round(customers['Total Spent'].sum(), 2)
check(
    "orders_clean total matches customers_clean Total Spent sum",
    orders_total == customers_total,
    f"£{orders_total} vs £{customers_total}" if orders_total != customers_total else "",
)

funnel_path = OUTPUTS_DIR / 'funnel_summary.csv'
if funnel_path.exists():
    funnel = pd.read_csv(funnel_path).iloc[0]
    check(
        "funnel_summary order count matches orders_clean row count",
        int(funnel['total_orders']) == len(orders),
        f"{int(funnel['total_orders'])} vs {len(orders)}" if int(funnel['total_orders']) != len(orders) else "",
    )

forecast_path = OUTPUTS_DIR / 'forecast_vs_actual_summary.csv'
if forecast_path.exists():
    forecast = pd.read_csv(forecast_path).iloc[0]
    check("forecast overlap window is non-empty (overlap_days > 0)", forecast['overlap_days'] > 0)

pricing_path = OUTPUTS_DIR / 'pricing_integrity_summary.csv'
integrity_score_pct = None
if pricing_path.exists():
    pricing = pd.read_csv(pricing_path).iloc[0]
    integrity_score_pct = float(pricing['integrity_score_pct'])
    expected_score = round(pricing['verified_real_discount_count'] / pricing['products_checked'] * 100, 1)
    check(
        "pricing integrity score is internally consistent with its own counts",
        abs(integrity_score_pct - expected_score) < 0.1,
        f"stated {integrity_score_pct}% vs recomputed {expected_score}%" if abs(integrity_score_pct - expected_score) >= 0.1 else "",
    )

per_product_pricing = OUTPUTS_DIR / 'pricing_integrity_check.csv'
if per_product_pricing.exists():
    per_product = pd.read_csv(per_product_pricing)
    check(
        "no product is double-counted across pricing statuses",
        per_product['Handle'].duplicated().sum() == 0,
    )

total_checks = len(checks)
passed_checks = sum(1 for c in checks if c['passed'])
failed_checks = total_checks - passed_checks
overall_status = 'HEALTHY' if failed_checks == 0 else 'NEEDS ATTENTION'

print(f"\n=== RESULT: {overall_status} ({passed_checks}/{total_checks} checks passed) ===")
if failed_checks:
    print("The following checks failed — do not treat this run's outputs as launch-ready until fixed:")
    for c in checks:
        if not c['passed']:
            print(f"  - {c['check_name']}" + (f" ({c['detail']})" if c['detail'] else ""))


# --
# SAVE SUMMARY
# --

summary = pd.DataFrame([{
    'products_row_count': len(products),
    'orders_row_count': len(orders),
    'customers_row_count': len(customers),
    'pricing_integrity_score_pct': integrity_score_pct,
    'checks_passed': passed_checks,
    'checks_total': total_checks,
    'overall_status': overall_status,
    'run_at': pd.Timestamp.now().isoformat(timespec='seconds'),
}])
summary.to_csv('../outputs/pipeline_health_summary.csv', index=False)

detail_df = pd.DataFrame(checks)
detail_df.to_csv('../outputs/pipeline_health_checks.csv', index=False)

print("\nSaved to outputs/pipeline_health_summary.csv and outputs/pipeline_health_checks.csv")

# Fail the pipeline run itself (non-zero exit) when a structural invariant
# is broken, rather than only reporting it — pipeline.py's own SUCCESS/
# FAILED summary should reflect launch-readiness, not just "each script ran".
sys.exit(1 if failed_checks else 0)
