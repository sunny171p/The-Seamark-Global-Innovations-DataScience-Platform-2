# Project 2 API

An internal API that exposes the real outputs of the `analytics/`
pipeline (product classification, pricing integrity, margin anomaly
detection, forecast-vs-actual, omnichannel visibility, affiliate
signups, pipeline health) as JSON, so a teammate — or another Seamark
system, like `Seamark_Smart3PL_Router` or `Seamark_Control_Center` —
can query them directly instead of opening a CSV by hand.

## Honest scope — read this before wiring anything up to it

This API does **not** predict per-product demand. It was built with
that in mind and deliberately left it out: this store has 7 real
orders spread across 275 products, which is nowhere near enough
history to fit a per-SKU forecast without the result being fabricated
precision dressed up as a model. `GET /forecast/summary` gives you the
real forecast Project 1 actually produced — a **store-wide** daily
revenue forecast — checked against real revenue, and says so in the
response itself (`scope` and `why_not_per_product` fields), so nothing
downstream mistakes it for a per-product number.

What genuinely is per-product, and is exposed as such:
- Category (rule-based) and text cluster (TF-IDF/K-Means), from `02_product_classification.py`
- Pricing integrity status and margin anomaly flag, from `05_pricing_integrity.py`

`GET /affiliates/summary` has the same kind of honest boundary: it's
signup and engagement counts from UpPromote's own export, not an
attribution report. UpPromote's export has no order-reference column, so
this API cannot and does not say whether any of the 7 real orders came
through an affiliate link — see `DATA_PROVENANCE.md`'s "Known gap".

## Why Flask, not FastAPI

FastAPI wasn't installable in the environment this was built in (no
PyPI access to it in that sandbox). Flask was already proven working
elsewhere in this body of work (`Seamark_Smart3PL_Router/api/app.py`
uses it for the routing API), so this uses the same, already-verified
stack rather than a framework that couldn't actually be installed and
tested.

## Running it

Development:
```
pip install -r requirements.txt
python main.py
```

Runs on `http://127.0.0.1:5050` by default. Override with the `API_HOST` /
`API_PORT` environment variables.

Production — Flask's own dev server prints its own warning that it isn't
meant for this; put a real WSGI server in front of the same `app` object
instead, nothing else here needs to change:
```
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5050 main:app
```

## Endpoints

| Method | Path | What it returns |
|---|---|---|
| GET | `/health` | Whether this API process loaded data successfully, and how many products |
| GET | `/products` | Every product handle currently in the catalogue |
| GET | `/products/<handle>` | One product's category, cluster, pricing status, margin anomaly flag |
| GET | `/forecast/summary` | The real store-wide forecast-vs-actual and capital-exposure numbers |
| GET | `/channels/omnichannel` | The Shopify-vs-Google-Shopping visibility comparison |
| GET | `/affiliates/summary` | UpPromote signup counts by status, verification and engagement — signups only, no order attribution (see below) |
| GET | `/pipeline/health` | Whether the pipeline's own structural checks (Stage 10 — `08_pipeline_health.py`, which runs last on purpose) passed on its last run — the launch-readiness gate, not this API's own status |

`/health` and `/pipeline/health` answer different questions: the first is
"is this API process up and did it load its files", the second is "did the
last `python pipeline.py` run actually produce internally-consistent
outputs". A healthy API process can still be serving data from a pipeline
run that this check flagged — check both before trusting a number for
something customer-facing.

## Data freshness

This API loads its data once, at startup, directly from `cleaned_data/`
and `outputs/`. It does not watch those files for changes. After
re-running `pipeline.py`, restart this API to pick up the new numbers
— it will not do so automatically.
