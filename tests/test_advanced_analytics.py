# ==
# test_advanced_analytics.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# These four checks cover the four "make it stronger" enhancements —
# product-text clustering, the funnel drop-off scenario, the forecast
# capital-exposure estimate, and margin anomaly detection. Same rule
# as every other test in this project: recompute independently from
# the saved outputs, don't just check that a column exists.

import pandas as pd
import pytest

from conftest import skip_if_missing


# --
# 1. PRODUCT-TEXT CLUSTERING (02_product_classification.py)
# --

def test_text_cluster_column_exists_and_is_fully_assigned(cleaned_data_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    assert "Text_Cluster" in products.columns, (
        "products_clean.csv has no Text_Cluster column — "
        "run 02_product_classification.py before this test."
    )
    assert products["Text_Cluster"].notna().all(), "Every product should have a cluster assignment."
    n_clusters = products["Text_Cluster"].nunique()
    assert 4 <= n_clusters <= 12, f"Expected k in the searched range 4-12, got {n_clusters} clusters."


def test_cluster_top_terms_file_covers_every_cluster(cleaned_data_dir, outputs_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    top_terms = pd.read_csv(outputs_dir / "cluster_top_terms.csv")

    expected_clusters = set(products["Text_Cluster"].unique())
    saved_clusters = set(top_terms["cluster"].unique())
    assert expected_clusters == saved_clusters, (
        "cluster_top_terms.csv doesn't cover exactly the clusters found in products_clean.csv."
    )
    # Every cluster's reported size should match how many products actually
    # carry that label — a mismatch would mean the two files went stale
    # relative to each other on some later run.
    actual_sizes = products["Text_Cluster"].value_counts().sort_index()
    saved_sizes = top_terms.set_index("cluster")["size"].sort_index()
    assert list(actual_sizes.values) == list(saved_sizes.values)


def test_category_vs_cluster_crosstab_row_totals_match_category_counts(cleaned_data_dir, outputs_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    crosstab = pd.read_csv(outputs_dir / "category_vs_cluster.csv", index_col=0)

    expected = products["Auto_Category"].value_counts().sort_index()
    actual = crosstab.sum(axis=1).sort_index()
    assert list(expected.index) == list(actual.index)
    assert list(expected.values) == list(actual.values)


# --
# 2. FUNNEL DROP-OFF SCENARIO (03_funnel_analysis.py)
# --

def test_gateway_and_channel_variance_flags_match_real_order_data(raw_data_dir, outputs_dir):
    """This is the check that keeps the funnel script honest — it
    recomputes payment-method/source variance straight from the raw
    order export and confirms the saved flags agree, rather than
    trusting the script's own claim that no friction point exists.
    """
    skip_if_missing(raw_data_dir / "orders_export.csv")
    raw_orders = pd.read_csv(raw_data_dir / "orders_export.csv", low_memory=False)
    order_level = raw_orders.groupby("Name", as_index=False).first()

    expected_gateway_variance = order_level["Payment Method"].nunique(dropna=True) > 1
    expected_channel_variance = order_level["Source"].nunique(dropna=True) > 1

    saved = pd.read_csv(outputs_dir / "funnel_summary.csv").iloc[0]
    assert bool(saved["gateway_variance_found"]) == expected_gateway_variance
    assert bool(saved["channel_variance_found"]) == expected_channel_variance


def test_scenario_revenue_recomputes_from_saved_aov_and_rates(outputs_dir):
    """The +5% scenario is a formula, not a fact pulled from data — so
    what this checks is that the formula was applied correctly to the
    real AOV and real conversion rate already saved, not that the
    numbers match some external source.
    """
    saved = pd.read_csv(outputs_dir / "funnel_summary.csv").iloc[0]

    if pd.isna(saved["aov_gbp"]) or pd.isna(saved["adjusted_conversion_rate_pct"]):
        pytest.skip("Scenario fields not computable for this data (missing AOV or conversion rate).")

    new_rate = saved["adjusted_conversion_rate_pct"] * 1.05
    expected_additional_orders = round(
        saved["adjusted_sessions"] * (new_rate - saved["adjusted_conversion_rate_pct"]) / 100, 2
    )
    expected_additional_revenue = round(expected_additional_orders * saved["aov_gbp"], 2)

    assert saved["scenario_additional_orders"] == pytest.approx(expected_additional_orders, abs=0.01)
    assert saved["scenario_additional_revenue_gbp"] == pytest.approx(expected_additional_revenue, abs=0.5)


# --
# 3. FORECAST CAPITAL-EXPOSURE ESTIMATE (04_forecast_vs_actual.py)
# --

def test_capital_at_risk_recomputes_from_error_and_real_margin(cleaned_data_dir, outputs_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    expected_avg_margin = round(products["Margin %"].dropna().mean(), 1)

    saved = pd.read_csv(outputs_dir / "forecast_vs_actual_summary.csv").iloc[0]
    assert saved["avg_margin_pct_used"] == pytest.approx(expected_avg_margin, abs=0.1)

    # FIXED (September 2026): 04_forecast_vs_actual.py only computes
    # capital_at_risk_gbp when the forecast OVERpredicted (error_gbp > 0) —
    # "dead capital from unsold stock" doesn't apply to an underprediction,
    # so that case leaves it blank/NaN on purpose instead of forcing a number
    # that wouldn't mean anything. This test used to assert a real number
    # unconditionally, which is exactly the always-overpredicts assumption
    # the forecast-honesty fix upstream removed.
    if saved["error_gbp"] > 0:
        expected_capital_at_risk = round(saved["error_gbp"] * (1 - expected_avg_margin / 100), 2)
        assert saved["capital_at_risk_gbp"] == pytest.approx(expected_capital_at_risk, abs=0.5)
    else:
        assert pd.isna(saved["capital_at_risk_gbp"]), (
            "capital_at_risk_gbp should be blank/NaN when the forecast did not overpredict "
            "(there's no unsold-stock capital to cost out)."
        )


def test_forecast_summary_has_no_fabricated_stock_quantity_columns(cleaned_data_dir):
    """Guards the honesty boundary directly: this catalogue has no
    inventory-quantity export, so nothing in the pipeline should ever
    introduce a stock-count or stockout-date column that looks like it
    came from real inventory data.
    """
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    forbidden = {"Inventory Quantity", "Stock On Hand", "Stockout Date"}
    assert forbidden.isdisjoint(products.columns), (
        "products_clean.csv has a stock-quantity-like column, but no inventory "
        "export exists for this catalogue — this would be fabricated data."
    )


# --
# 4. MARGIN ANOMALY DETECTION (05_pricing_integrity.py)
# --

def test_margin_anomaly_count_matches_iqr_recomputation(cleaned_data_dir, outputs_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    margin = products["Margin %"].dropna()

    q1, q3 = margin.quantile(0.25), margin.quantile(0.75)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    expected_anomaly_count = int((margin < lower_fence).sum())

    saved = pd.read_csv(outputs_dir / "pricing_integrity_summary.csv").iloc[0]
    assert int(saved["margin_anomaly_count"]) == expected_anomaly_count
    assert saved["margin_anomaly_threshold_pct"] == pytest.approx(round(lower_fence, 1), abs=0.1)


def test_margin_anomaly_check_file_only_contains_flagged_products(cleaned_data_dir, outputs_dir):
    flagged = pd.read_csv(outputs_dir / "margin_anomaly_check.csv")
    if len(flagged) == 0:
        pytest.skip("No margin anomalies found on this catalogue — nothing to check.")

    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    margin = products["Margin %"].dropna()
    q1, q3 = margin.quantile(0.25), margin.quantile(0.75)
    lower_fence = q1 - 1.5 * (q3 - q1)

    assert (flagged["Margin %"] < lower_fence).all(), (
        "margin_anomaly_check.csv contains a product whose margin is not "
        "actually below the IQR anomaly threshold."
    )
