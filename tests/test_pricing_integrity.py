# ==
# test_pricing_integrity.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# This is the single most customer-facing number this project
# produces — feeding directly into the Trust Score shown on the
# storefront. If this check ever drifted or got miscounted, it would
# mean showing customers a false "verified real discount" claim,
# which is exactly the kind of thing this whole project exists to
# prevent. Recomputed independently here, the same pattern as every
# other headline number in this project.

import pandas as pd
import pytest


def test_pricing_integrity_matches_recomputation(cleaned_data_dir, outputs_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    checked = products[products["Variant Compare At Price"].notna()]

    expected_misleading = int((checked["Variant Price"] > checked["Variant Compare At Price"]).sum())
    expected_verified = int((checked["Variant Price"] < checked["Variant Compare At Price"]).sum())

    saved = pd.read_csv(outputs_dir / "pricing_integrity_summary.csv").iloc[0]
    assert int(saved["misleading_discount_count"]) == expected_misleading
    assert int(saved["verified_real_discount_count"]) == expected_verified
    assert int(saved["products_checked"]) == len(checked)


def test_no_product_is_double_counted_across_pricing_statuses(outputs_dir):
    per_product = pd.read_csv(outputs_dir / "pricing_integrity_check.csv")
    assert per_product["Handle"].duplicated().sum() == 0


def test_integrity_score_is_internally_consistent(outputs_dir):
    summary = pd.read_csv(outputs_dir / "pricing_integrity_summary.csv").iloc[0]
    expected_score = round(summary["verified_real_discount_count"] / summary["products_checked"] * 100, 1)
    assert summary["integrity_score_pct"] == pytest.approx(expected_score, abs=0.1)
