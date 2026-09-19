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
