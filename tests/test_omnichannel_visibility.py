# ==
# test_omnichannel_visibility.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The Merchant Center numbers in this stage aren't a CSV export like
# everything else in this project — they were read manually off a live
# dashboard. That makes it MORE important to test, not less: these
# checks guard against a manual transcription drifting silently out of
# sync with the source file, and against the website-vs-Google-Shopping
# comparison ever collapsing the two different time windows into one
# without saying so.

import pandas as pd
import pytest


def test_website_numbers_match_funnel_summary(outputs_dir):
    funnel = pd.read_csv(outputs_dir / "funnel_summary.csv").iloc[0]
    omni = pd.read_csv(outputs_dir / "omnichannel_visibility_summary.csv").iloc[0]

    assert int(omni["website_sessions"]) == int(funnel["total_sessions"])
    assert int(omni["website_orders"]) == int(funnel["total_orders"])
    assert omni["website_conversion_rate_pct"] == pytest.approx(funnel["conversion_rate_pct"], abs=0.001)


def test_google_shopping_numbers_match_manual_observation_file(raw_data_dir, outputs_dir):
    """Guards against the summary silently drifting from the source
    observation file — if someone updates merchant_center_observation.csv
    with fresher numbers, this test forces the summary to be regenerated
    to match, not left stale.
    """
    merchant_center = pd.read_csv(raw_data_dir / "merchant_center_observation.csv")
    omni = pd.read_csv(outputs_dir / "omnichannel_visibility_summary.csv").iloc[0]

    expected_clicks = int(merchant_center.loc[merchant_center["metric"] == "Ads + Organic - Clicks", "value"].iloc[0])
    expected_purchases = int(merchant_center.loc[merchant_center["metric"] == "Organic - Purchases", "value"].iloc[0])

    assert int(omni["google_shopping_clicks"]) == expected_clicks
    assert int(omni["google_shopping_purchases"]) == expected_purchases


def test_time_windows_are_stated_and_different(outputs_dir):
    """The website window and the Google Shopping window are NOT the
    same date range. This test exists specifically to catch a future
    edit that quietly makes them look identical without actually
    reconciling the underlying data.
    """
    omni = pd.read_csv(outputs_dir / "omnichannel_visibility_summary.csv").iloc[0]
    assert pd.notna(omni["website_window"]) and omni["website_window"] != ""
    assert pd.notna(omni["google_shopping_window"]) and omni["google_shopping_window"] != ""
    assert omni["website_window"] != omni["google_shopping_window"]


def test_data_source_note_discloses_manual_reading(outputs_dir):
    """This is the honesty tripwire for this whole stage — the summary
    file must keep stating that the Google Shopping figures were read
    manually, not exported, so nobody downstream mistakes them for a
    native Shopify/Merchant Center export like every other file in this
    project.
    """
    omni = pd.read_csv(outputs_dir / "omnichannel_visibility_summary.csv").iloc[0]
    note = str(omni["data_source_note"]).lower()
    assert "manually" in note or "no csv export" in note
