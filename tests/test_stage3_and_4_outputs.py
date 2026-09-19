# ==
# test_stage3_and_4_outputs.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# Same reasoning as test_pipeline_outputs.py in Project 1 — the funnel
# and forecast-accuracy figures are headline numbers for this project,
# so they get independently recomputed here and checked against what
# the scripts actually saved, rather than trusted on a single run.

import pandas as pd
import pytest

from conftest import skip_if_missing

# FIXED (September 2026): matches the same date-based cutoff used in
# analytics/04_forecast_vs_actual.py. Project 1's forecast file used to have
# exactly 11 sparse historical rows, so slicing with iloc[11:] isolated the
# future block; once that history became a continuous 138-row zero-filled
# daily series, the same fixed row count started grabbing the wrong rows.
# Filtering by date instead of position doesn't break the next time Project
# 1's training window changes length.
PROJECT1_LAST_REAL_ORDER_DATE = pd.Timestamp("2026-08-04")


def test_funnel_conversion_rate_matches_recomputation(raw_data_dir, cleaned_data_dir, outputs_dir):
    skip_if_missing(cleaned_data_dir / "orders_clean.csv")
    visitors = pd.read_csv(raw_data_dir / "visitors_over_time.csv")
    orders = pd.read_csv(cleaned_data_dir / "orders_clean.csv")

    expected_sessions = int(visitors["Sessions"].sum())
    expected_orders = len(orders)
    expected_conversion = round(expected_orders / expected_sessions * 100, 3)

    saved = pd.read_csv(outputs_dir / "funnel_summary.csv").iloc[0]
    assert int(saved["total_sessions"]) == expected_sessions
    assert int(saved["total_orders"]) == expected_orders
    assert saved["conversion_rate_pct"] == pytest.approx(expected_conversion, abs=0.001)


def test_bot_session_count_matches_recomputation(raw_data_dir, outputs_dir):
    location = pd.read_csv(raw_data_dir / "sessions_by_location.csv")
    data_center_towns = ["Prineville", "The Dalles", "Council Bluffs", "Altoona", "Boardman", "Luleå"]

    expected_bot_sessions = int(location[location["Session city"].isin(data_center_towns)]["Sessions"].sum())

    saved = pd.read_csv(outputs_dir / "funnel_summary.csv").iloc[0]
    assert int(saved["likely_bot_sessions"]) == expected_bot_sessions


def test_forecast_vs_actual_matches_recomputation(project_root, cleaned_data_dir, raw_data_dir, outputs_dir):
    skip_if_missing(cleaned_data_dir / "orders_clean.csv")
    forecast = pd.read_csv(raw_data_dir / "project1_sales_forecast_90days.csv")
    orders = pd.read_csv(cleaned_data_dir / "orders_clean.csv")

    forecast["ds"] = pd.to_datetime(forecast["ds"])
    future = forecast.sort_values("ds").reset_index(drop=True)
    future = future[future["ds"] > PROJECT1_LAST_REAL_ORDER_DATE]
    overlap = future[(future["ds"] >= "2026-08-01") & (future["ds"] <= "2026-09-14")]

    expected_predicted = round(overlap["yhat"].sum(), 2)
    expected_actual = round(orders["Total"].sum(), 2)

    saved = pd.read_csv(outputs_dir / "forecast_vs_actual_summary.csv").iloc[0]
    assert saved["predicted_total_gbp"] == pytest.approx(expected_predicted, abs=0.01)
    assert saved["actual_total_gbp"] == pytest.approx(expected_actual, abs=0.01)


def test_forecast_overlap_window_is_within_both_data_ranges(raw_data_dir, outputs_dir):
    """Guards against the overlap window silently drifting outside the
    range either dataset actually covers, which would make the
    comparison meaningless without necessarily erroring.
    """
    forecast = pd.read_csv(raw_data_dir / "project1_sales_forecast_90days.csv")
    forecast["ds"] = pd.to_datetime(forecast["ds"])
    future = forecast.sort_values("ds").reset_index(drop=True)
    future = future[future["ds"] > PROJECT1_LAST_REAL_ORDER_DATE]

    saved = pd.read_csv(outputs_dir / "forecast_vs_actual_summary.csv").iloc[0]
    assert saved["overlap_days"] > 0, "No overlap between the forecast window and real order data — comparison is meaningless."
    assert saved["overlap_days"] <= len(future)
