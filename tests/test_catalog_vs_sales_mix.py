# ==
# test_catalog_vs_sales_mix.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# Same rule as every other test in this project: recompute independently
# from the raw/cleaned files and check the saved output agrees, rather
# than trusting 09_catalog_vs_sales_mix.py's own arithmetic. This also
# guards the specific honesty point that script is built around — the
# "expected" side of the comparison must be this store's REAL catalogue
# mix, never a simulated or invented number.

import pandas as pd
import pytest


def _recompute_comparison(cleaned_data_dir, raw_data_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    raw_products = pd.read_csv(raw_data_dir / "products_export.csv", low_memory=False)
    line_items = pd.read_csv(cleaned_data_dir / "order_line_items_clean.csv")

    sku_to_handle = (
        raw_products.dropna(subset=["Variant SKU"])
        .drop_duplicates("Variant SKU")
        .set_index("Variant SKU")["Handle"]
    )
    title_to_handle = (
        raw_products.dropna(subset=["Title"])
        .drop_duplicates("Title")
        .set_index("Title")["Handle"]
    )

    line_items = line_items.copy()
    line_items["matched_handle"] = line_items["Lineitem sku"].map(sku_to_handle)
    still_missing = line_items["matched_handle"].isna()
    line_items.loc[still_missing, "matched_handle"] = (
        line_items.loc[still_missing, "Lineitem name"].map(title_to_handle)
    )

    line_items = line_items.merge(
        products[["Handle", "Auto_Category"]],
        left_on="matched_handle", right_on="Handle", how="left",
    )
    line_items["line_revenue_gbp"] = line_items["Lineitem quantity"] * line_items["Lineitem price"]

    catalog_counts = products["Auto_Category"].value_counts()
    catalog_pct = (catalog_counts / catalog_counts.sum() * 100).round(1)

    matched_items = line_items.dropna(subset=["Auto_Category"])
    sales_revenue = matched_items.groupby("Auto_Category")["line_revenue_gbp"].sum()

    return catalog_counts, catalog_pct, sales_revenue, line_items


def test_every_real_line_item_matches_a_real_product(cleaned_data_dir, raw_data_dir):
    """The whole point of this script is using 100% real data on both
    sides — if a line item stopped matching a real product (e.g. after
    a catalogue refresh), the sales-mix side would silently understate
    revenue rather than error, so this checks the match rate directly.
    """
    _, _, _, line_items = _recompute_comparison(cleaned_data_dir, raw_data_dir)
    unmatched = line_items[line_items["Auto_Category"].isna()]
    assert unmatched.empty, (
        f"{len(unmatched)} real line item(s) didn't match any real product by SKU or title: "
        f"{unmatched['Lineitem name'].tolist()}"
    )


def test_catalog_vs_sales_mix_matches_recomputation(cleaned_data_dir, raw_data_dir, outputs_dir):
    catalog_counts, catalog_pct, sales_revenue, _ = _recompute_comparison(cleaned_data_dir, raw_data_dir)
    saved = pd.read_csv(outputs_dir / "catalog_vs_sales_mix.csv").set_index("auto_category")

    for category, expected_count in catalog_counts.items():
        assert int(saved.loc[category, "catalog_product_count"]) == int(expected_count)
        assert saved.loc[category, "catalog_pct"] == pytest.approx(catalog_pct[category], abs=0.1)

    for category, expected_revenue in sales_revenue.items():
        assert saved.loc[category, "real_sales_revenue_gbp"] == pytest.approx(round(expected_revenue, 2), abs=0.01)


def test_catalog_pct_sums_to_100(outputs_dir):
    saved = pd.read_csv(outputs_dir / "catalog_vs_sales_mix.csv")
    assert saved["catalog_pct"].sum() == pytest.approx(100.0, abs=0.5)


def test_real_sales_pct_sums_to_100_when_any_sales_matched(outputs_dir):
    saved = pd.read_csv(outputs_dir / "catalog_vs_sales_mix.csv")
    if saved["real_sales_revenue_gbp"].sum() == 0:
        pytest.skip("No real sales revenue matched to a category yet.")
    assert saved["real_sales_pct"].sum() == pytest.approx(100.0, abs=0.5)


def test_real_sales_revenue_total_matches_real_line_items(cleaned_data_dir, raw_data_dir, outputs_dir):
    """Every pound of real, matched line-item revenue should show up
    somewhere in the saved file — nothing silently dropped.
    """
    _, _, _, line_items = _recompute_comparison(cleaned_data_dir, raw_data_dir)
    expected_total = round((line_items["Lineitem quantity"] * line_items["Lineitem price"])[
        line_items["Auto_Category"].notna()
    ].sum(), 2)

    saved = pd.read_csv(outputs_dir / "catalog_vs_sales_mix.csv")
    assert saved["real_sales_revenue_gbp"].sum() == pytest.approx(expected_total, abs=0.01)
