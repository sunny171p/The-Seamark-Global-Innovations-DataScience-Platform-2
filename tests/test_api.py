# ==
# test_api.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The API is a new way for something OTHER than a human to read this
# project's outputs, so it deserves its own tests — not just "does it
# start", but "does a real product handle return the real numbers the
# pipeline computed for it", and "does the forecast endpoint actually
# state its own limitation rather than silently dropping it".

import sys
from pathlib import Path

import pandas as pd
import pytest

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))


@pytest.fixture(scope="module")
def client():
    import main as api_main
    api_main.app.config["TESTING"] = True
    return api_main.app.test_client()


def test_health_reports_products_loaded(client, cleaned_data_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["products_loaded"] == len(products)


def test_products_list_matches_cleaned_data(client, cleaned_data_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    resp = client.get("/products")
    body = resp.get_json()
    assert body["count"] == len(products)
    assert set(body["handles"]) == set(products["Handle"])


def test_product_profile_matches_real_data_for_a_known_handle(client, cleaned_data_dir):
    products = pd.read_csv(cleaned_data_dir / "products_clean.csv")
    sample = products.iloc[0]
    handle = sample["Handle"]

    resp = client.get(f"/products/{handle}")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["handle"] == handle
    assert body["title"] == sample["Title"]
    assert body["auto_category"] == sample["Auto_Category"]
    assert body["text_cluster"] == int(sample["Text_Cluster"])


def test_product_profile_404_for_unknown_handle(client):
    resp = client.get("/products/this-handle-does-not-exist-anywhere")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_forecast_summary_matches_pipeline_output_and_states_its_own_scope(client, outputs_dir):
    saved = pd.read_csv(outputs_dir / "forecast_vs_actual_summary.csv").iloc[0]
    resp = client.get("/forecast/summary")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["predicted_total_gbp"] == pytest.approx(saved["predicted_total_gbp"], abs=0.01)
    assert body["actual_total_gbp"] == pytest.approx(saved["actual_total_gbp"], abs=0.01)
    # The honesty tripwire for this endpoint: it must always disclose that
    # this is a store-wide number, not a per-product prediction — a future
    # edit that silently drops this disclosure should fail this test.
    assert "per-product" in body["why_not_per_product"].lower()
    assert "store-wide" in body["scope"].lower()


def test_omnichannel_endpoint_matches_pipeline_output(client, outputs_dir):
    saved = pd.read_csv(outputs_dir / "omnichannel_visibility_summary.csv").iloc[0]
    resp = client.get("/channels/omnichannel")
    assert resp.status_code == 200
    body = resp.get_json()
    assert int(body["website_orders"]) == int(saved["website_orders"])
    assert int(body["google_shopping_purchases"]) == int(saved["google_shopping_purchases"])


def test_affiliate_summary_endpoint_matches_pipeline_output(client, outputs_dir):
    saved = pd.read_csv(outputs_dir / "affiliate_summary.csv").iloc[0]
    resp = client.get("/affiliates/summary")
    assert resp.status_code == 200
    body = resp.get_json()

    assert int(body["total_signups"]) == int(saved["total_signups"])
    assert int(body["active_count"]) == int(saved["active_count"])
    # The honesty tripwire for this endpoint, same idea as the forecast
    # one above — it must keep disclosing that this is signups only, no
    # order attribution, rather than a future edit quietly dropping that.
    assert body["attribution_available"] is False
    note = body["attribution_gap_note"].lower()
    assert "known gap" in note or "no order-reference" in note
    assert isinstance(body["by_status"], list) and len(body["by_status"]) > 0


def test_pipeline_health_endpoint_matches_pipeline_output(client, outputs_dir):
    saved = pd.read_csv(outputs_dir / "pipeline_health_summary.csv").iloc[0]
    resp = client.get("/pipeline/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["overall_status"] == saved["overall_status"]
    assert int(body["checks_passed"]) == int(saved["checks_passed"])
    assert int(body["checks_total"]) == int(saved["checks_total"])


def test_unknown_route_returns_json_404(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()
