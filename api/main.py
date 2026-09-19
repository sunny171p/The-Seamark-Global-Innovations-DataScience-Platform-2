# ==
# main.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# API layer
# ==
#
# WHY THIS EXISTS:
# Everything in analytics/ so far runs as a batch script and writes a
# CSV. That's fine for one person reading a report, but it means
# nobody else — and nothing else, like the Smart3PL Router or a future
# storefront widget — can ask this pipeline a question directly. This
# turns the pipeline's real outputs into a small internal API, so a
# teammate (or another one of Seamark's own systems) can query it by
# product handle instead of opening a CSV by hand.
#
# WHY THIS IS FLASK, NOT FASTAPI:
# FastAPI could not be installed in the sandbox this was built in (no
# PyPI access to it), and Flask was already proven working elsewhere
# in this project (Seamark_Smart3PL_Router/api/app.py). Same pattern,
# same honesty: build it with what's actually available and verified
# to run, not what looks more fashionable on paper.
#
# WHAT THIS DELIBERATELY DOES NOT DO:
# It does NOT expose a "predict demand for product X next month"
# endpoint. That would need a per-product demand model, and this
# store has 7 real orders spread across 275 products — nowhere near
# enough history to fit a per-SKU forecast without the result being
# fabricated precision. What Project 1's Prophet model actually
# forecasts is STORE-WIDE daily revenue, not per-product demand, so
# that's exactly the scope this API exposes it at: GET /forecast/summary
# returns the real aggregate forecast-vs-actual and capital-exposure
# numbers from 04_forecast_vs_actual.py, honestly labelled as
# store-wide, with no per-product number invented to fill the gap.
# What IS genuinely available per product — pricing integrity, margin
# anomaly status, category, and text cluster — is exposed per handle,
# because those signals really were computed at product level.
#
# HOW TO RUN (development):
#   pip install -r requirements.txt
#   python main.py
#   Then, e.g.: curl http://127.0.0.1:5050/products/<a-real-handle>
#
# HOW TO RUN (production):
#   Flask's own dev server (what `python main.py` starts) prints its own
#   warning that it isn't meant for production — use a real WSGI server
#   in front of this same `app` object instead, e.g.:
#     pip install gunicorn
#     gunicorn -w 2 -b 0.0.0.0:5050 main:app
#   Nothing else about this file needs to change to run that way.
# ==

import os
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DATA_DIR = PROJECT_ROOT / "cleaned_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def _load_data():
    """Loads every CSV this API serves from, once, at startup. This is
    a small, batch-computed dataset (275 products) — reloading it on
    every request would be pointless overhead, and the underlying
    files only change when the pipeline is re-run, not live.
    """
    data = {}

    products = pd.read_csv(CLEANED_DATA_DIR / "products_clean.csv")
    data["products"] = products.set_index("Handle")

    pricing_path = OUTPUTS_DIR / "pricing_integrity_check.csv"
    data["pricing"] = (
        pd.read_csv(pricing_path).set_index("Handle") if pricing_path.exists() else pd.DataFrame()
    )

    margin_anomaly_path = OUTPUTS_DIR / "margin_anomaly_check.csv"
    if margin_anomaly_path.exists():
        margin_df = pd.read_csv(margin_anomaly_path)
        data["margin_anomaly_handles"] = set(margin_df["Handle"]) if len(margin_df) else set()
    else:
        data["margin_anomaly_handles"] = set()

    cluster_terms_path = OUTPUTS_DIR / "cluster_top_terms.csv"
    data["cluster_terms"] = (
        pd.read_csv(cluster_terms_path).set_index("cluster") if cluster_terms_path.exists() else pd.DataFrame()
    )

    forecast_path = OUTPUTS_DIR / "forecast_vs_actual_summary.csv"
    data["forecast_summary"] = (
        pd.read_csv(forecast_path).iloc[0].to_dict() if forecast_path.exists() else {}
    )

    omni_path = OUTPUTS_DIR / "omnichannel_visibility_summary.csv"
    data["omnichannel_summary"] = (
        pd.read_csv(omni_path).iloc[0].to_dict() if omni_path.exists() else {}
    )

    affiliate_path = OUTPUTS_DIR / "affiliate_summary.csv"
    data["affiliate_summary"] = (
        pd.read_csv(affiliate_path).iloc[0].to_dict() if affiliate_path.exists() else {}
    )

    affiliate_status_path = OUTPUTS_DIR / "affiliate_by_status.csv"
    data["affiliate_by_status"] = (
        pd.read_csv(affiliate_status_path).to_dict(orient="records") if affiliate_status_path.exists() else []
    )

    pipeline_health_path = OUTPUTS_DIR / "pipeline_health_summary.csv"
    data["pipeline_health"] = (
        pd.read_csv(pipeline_health_path).iloc[0].to_dict() if pipeline_health_path.exists() else {}
    )

    return data


DATA = _load_data()


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "products_loaded": int(len(DATA["products"])),
        "note": "Data is loaded once at startup from analytics/ pipeline outputs. "
                "Restart this API after re-running pipeline.py to pick up fresh numbers.",
    })


@app.route("/products")
def list_products():
    handles = list(DATA["products"].index)
    return jsonify({
        "count": len(handles),
        "handles": handles,
    })


@app.route("/products/<handle>")
def product_profile(handle):
    """The genuinely useful per-product endpoint — combines real
    signals from three separate pipeline stages (classification,
    pricing integrity, margin anomaly detection) into one lookup, the
    same combination trust_score_engine.py already does for the
    storefront, exposed here for internal/team use instead.
    """
    if handle not in DATA["products"].index:
        return jsonify({"error": f"No product found with handle '{handle}'"}), 404

    product = DATA["products"].loc[handle]

    pricing_status = None
    if not DATA["pricing"].empty and handle in DATA["pricing"].index:
        pricing_status = DATA["pricing"].loc[handle, "Pricing Status"]

    cluster_id = product.get("Text_Cluster")
    cluster_terms = None
    if cluster_id is not None and not DATA["cluster_terms"].empty:
        try:
            cluster_terms = DATA["cluster_terms"].loc[int(cluster_id), "top_terms"]
        except (KeyError, ValueError):
            cluster_terms = None

    return jsonify({
        "handle": handle,
        "title": product.get("Title"),
        "auto_category": product.get("Auto_Category"),
        "text_cluster": int(cluster_id) if pd.notna(cluster_id) else None,
        "text_cluster_top_terms": cluster_terms,
        "shipping_destination": product.get("Shipping Destination"),
        "variant_price_gbp": float(product.get("Variant Price")) if pd.notna(product.get("Variant Price")) else None,
        "margin_pct": float(product.get("Margin %")) if pd.notna(product.get("Margin %")) else None,
        "pricing_status": pricing_status,
        "margin_anomaly": handle in DATA["margin_anomaly_handles"],
    })


@app.route("/forecast/summary")
def forecast_summary():
    """STORE-WIDE only — see the module docstring above for exactly
    why this is not a per-product endpoint.
    """
    if not DATA["forecast_summary"]:
        return jsonify({"error": "No forecast summary available — run 04_forecast_vs_actual.py first"}), 404

    response = dict(DATA["forecast_summary"])
    response["scope"] = "store-wide daily revenue forecast, NOT per-product demand"
    response["why_not_per_product"] = (
        "This store has 7 real orders across 275 products — not enough history "
        "to fit a per-product demand model without fabricating precision. "
        "This endpoint reports the real, store-wide forecast-vs-actual figures "
        "from 04_forecast_vs_actual.py instead."
    )
    return jsonify(response)


@app.route("/channels/omnichannel")
def omnichannel_summary():
    if not DATA["omnichannel_summary"]:
        return jsonify({"error": "No omnichannel summary available — run 06_omnichannel_visibility.py first"}), 404
    return jsonify(dict(DATA["omnichannel_summary"]))


@app.route("/affiliates/summary")
def affiliate_summary():
    """Signup-level engagement numbers only — see the module docstring's
    sibling note in 07_affiliate_analysis.py. This deliberately does not
    and cannot say whether any affiliate drove a real sale.
    """
    if not DATA["affiliate_summary"]:
        return jsonify({"error": "No affiliate summary available — run 07_affiliate_analysis.py first"}), 404

    response = dict(DATA["affiliate_summary"])
    response["by_status"] = DATA["affiliate_by_status"]
    return jsonify(response)


@app.route("/pipeline/health")
def pipeline_health():
    """Launch-readiness snapshot from Stage 10 (08_pipeline_health.py,
    which runs last on purpose — see pipeline.py's header comment) —
    whether the pipeline's own structural invariants held on its last
    run, not whether this API process itself is up (that's what GET
    /health answers).
    """
    if not DATA["pipeline_health"]:
        return jsonify({"error": "No pipeline health summary available — run 08_pipeline_health.py first"}), 404
    return jsonify(dict(DATA["pipeline_health"]))


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(_e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "5050"))
    print(f"Loaded {len(DATA['products'])} products from {CLEANED_DATA_DIR}")
    app.run(host=host, port=port, debug=False)
