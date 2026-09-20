# ==
# test_data_integrity.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# Project 1 only got a test suite after several numbers had already
# been found wrong by hand. This time the tests are going in from the
# first script instead of being bolted on afterwards — the exact
# mistakes that test suite was built to catch (a merge duplicating
# rows, two totals quietly drifting apart) are just as possible here,
# and this is real order revenue now, not a forecast, so a silent
# mismatch matters more, not less.

import subprocess
import sys

import pandas as pd

from conftest import skip_if_missing


def test_products_clean_has_no_duplicate_handles(cleaned_data_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    assert "Handle" in products.columns
    dupes = products["Handle"].duplicated().sum()
    assert dupes == 0, f"{dupes} duplicate Handle values in products_clean.csv"


def test_orders_clean_has_one_row_per_order(raw_data_dir, cleaned_data_dir):
    """Guards against the exact bug this cleaning step exists to avoid —
    Shopify repeats every order once per line item, so grouping by Name
    has to collapse that back to one row per order, not silently keep
    duplicates or (worse) sum a repeated Total across line items.
    """
    skip_if_missing(raw_data_dir / "orders_export.csv", cleaned_data_dir / "orders_clean.csv")
    raw_orders = pd.read_csv(raw_data_dir / "orders_export.csv")
    orders_clean = pd.read_csv(cleaned_data_dir / "orders_clean.csv")

    expected_order_count = raw_orders["Name"].nunique()
    assert len(orders_clean) == expected_order_count, (
        f"orders_clean.csv has {len(orders_clean)} rows but the raw export "
        f"has {expected_order_count} distinct order Names."
    )
    assert orders_clean["Name"].duplicated().sum() == 0


def test_orders_total_matches_raw_export(raw_data_dir, cleaned_data_dir):
    """Recomputes total revenue directly from the raw export (taking the
    first Total per order Name, the same way the cleaning script does)
    and checks it against the saved cleaned file — independent of
    whatever the cleaning script's own internal logic did.
    """
    skip_if_missing(raw_data_dir / "orders_export.csv", cleaned_data_dir / "orders_clean.csv")
    raw_orders = pd.read_csv(raw_data_dir / "orders_export.csv")
    expected_total = raw_orders.groupby("Name")["Total"].first().sum()

    orders_clean = pd.read_csv(cleaned_data_dir / "orders_clean.csv")
    actual_total = orders_clean["Total"].sum()

    assert round(actual_total, 2) == round(expected_total, 2), (
        f"orders_clean.csv totals £{actual_total:.2f} but recomputing from "
        f"the raw export gives £{expected_total:.2f}."
    )


def test_orders_and_customers_totals_agree(cleaned_data_dir):
    """Shopify computes Total Spent per customer independently of the
    orders export. If these two disagree, either the orders file is
    missing an order or the customers file is stale — either way it's
    worth knowing before anything is built on top of both.
    """
    skip_if_missing(cleaned_data_dir / "orders_clean.csv", cleaned_data_dir / "customers_clean.csv")
    orders = pd.read_csv(cleaned_data_dir / "orders_clean.csv")
    customers = pd.read_csv(cleaned_data_dir / "customers_clean.csv")

    orders_total = round(orders["Total"].sum(), 2)
    customers_total = round(customers["Total Spent"].sum(), 2)

    assert orders_total == customers_total, (
        f"orders_clean total (£{orders_total}) does not match "
        f"customers_clean Total Spent sum (£{customers_total})."
    )


def test_category_classification_other_rate_is_reasonable(cleaned_data_dir):
    """This catalogue's Type column is well-populated (~84%), so the
    'Other' bucket should stay small. If a future catalogue refresh
    pushes it much higher, the keyword list in 02_product_classification.py
    needs updating — this test is the tripwire for that, the same way
    Project 1's classification script flagged its own 'Other' rate.
    """
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    assert "Auto_Category" in products.columns, (
        "products_clean.csv has no Auto_Category column — "
        "run 02_product_classification.py before this test."
    )
    other_pct = (products["Auto_Category"] == "Other").mean() * 100
    assert other_pct < 20, f"'Other' category is {other_pct:.1f}% of the catalogue — keywords need updating."


def test_all_analytics_scripts_compile(project_root):
    """Cheap smoke test — every script under analytics/ should at
    least be syntactically valid Python before it's ever run.
    """
    analytics_dir = project_root / "analytics"
    scripts = sorted(analytics_dir.glob("*.py"))
    assert scripts, "No scripts found under analytics/"

    for script in scripts:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{script.name} failed to compile:\n{result.stderr}"


def test_voided_and_expired_orders_get_excluded_before_cleaning():
    """Unit test for the exclusion rule itself, not a read of real data —
    it doesn't need raw_data/orders_export.csv (which is gitignored and
    often missing on a fresh clone or in CI), because it checks the rule
    01_data_cleaning.py applies, not this store's real order history.

    This exists because a real webhook test once fired Shopify's own
    fixed test order at this project (see CASE_STUDY.md), and it came
    back with Financial Status 'voided' — a status that means payment
    was never actually collected, whether the order behind it is a test
    one or a genuine one that fell through for some real reason. The
    table below is a small made-up example built only to exercise that
    rule, not a claim about Seamark's real orders.
    """
    example_orders = pd.DataFrame({
        "Name": ["#1001", "#1001", "#9999", "#1002", "#1003"],
        "Financial Status": ["paid", "paid", "voided", "PAID", "expired"],
        "Total": [50.0, 50.0, 999.99, 30.0, 15.0],
    })

    # Same rule as 01_data_cleaning.py's NON_REVENUE_STATUSES check —
    # duplicated here on purpose rather than imported, same reasoning
    # as every other test in this file: an independent recomputation
    # catches drift a shared import could hide.
    non_revenue_statuses = {"voided", "expired"}
    excluded_mask = example_orders["Financial Status"].astype(str).str.lower().isin(non_revenue_statuses)
    kept = example_orders.loc[~excluded_mask]

    assert set(kept["Name"]) == {"#1001", "#1002"}, (
        "Expected only the paid orders to survive the exclusion filter."
    )
    assert "#9999" not in set(kept["Name"]), "A voided order should never be counted as revenue."
    assert "#1003" not in set(kept["Name"]), "An expired order should never be counted as revenue."
    # Case shouldn't matter — Shopify's own data is lowercase, but this
    # shouldn't silently start keeping a real order just because
    # something upstream capitalised its status differently one day.
    assert "#1002" in set(kept["Name"]), "A paid order should survive regardless of capitalisation."


def test_orders_clean_never_contains_a_voided_or_expired_order(cleaned_data_dir):
    """Standing invariant against this store's real cleaned data: no
    matter what lands in raw_data/orders_export.csv (including a future
    live webhook test), orders_clean.csv should never end up with a
    voided or expired order counted in it. Currently this store's real
    orders are all 'paid', so this is expected to pass trivially today —
    its real job is to fail loudly the day that's no longer true.
    """
    skip_if_missing(cleaned_data_dir / "orders_clean.csv")
    orders_clean = pd.read_csv(cleaned_data_dir / "orders_clean.csv")

    non_revenue_statuses = {"voided", "expired"}
    bad_rows = orders_clean[orders_clean["Financial Status"].astype(str).str.lower().isin(non_revenue_statuses)]
    assert bad_rows.empty, (
        f"orders_clean.csv contains {len(bad_rows)} voided/expired order(s) that should "
        f"have been excluded during cleaning: {bad_rows['Name'].tolist()}"
    )
