# Project 2 Dashboard (Streamlit + Supabase)

A single-screen view of what `analytics/` and `api/` already computed:
products, pricing integrity issues, checkout/conversion rate, affiliate
signups and engagement, the store-wide AI forecast vs actual, and a
pipeline health / launch-readiness panel — the same real numbers the CSVs
in `outputs/` and the Flask API already serve, just laid out so you can see
the store's health at a glance instead of opening several files. The
sidebar always shows a live HEALTHY / NEEDS ATTENTION badge from
`08_pipeline_health.py` (Stage 10 — it runs last on purpose, see
`pipeline.py`'s header comment), so a stale or broken pipeline run is
visible before you trust anything else on the screen.

## Two ways to run it

### 1. Local CSVs — zero setup

```
python pipeline.py                          # from the project root, if you haven't already
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

That's it. `dashboard/data_loader.py` reads straight from `cleaned_data/`
and `outputs/` when no Supabase credentials are configured, so this works
immediately with no external account.

### 2. Supabase — for a hosted/shared dashboard

Use this if you want the dashboard reachable from somewhere other than
your own machine, or want another Seamark system (Smart3PL Router, Control
Center) reading the same numbers Supabase holds.

1. Create a free project at [supabase.com](https://supabase.com).
2. Open the SQL editor and run `supabase/schema.sql` once — creates the
   tables.
3. Copy `supabase/.env.example` to `supabase/.env` and fill in your
   project's `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (Project
   Settings > API).
4. `pip install -r supabase/requirements.txt && python supabase/sync_to_supabase.py`
   — pushes the real pipeline outputs up. Re-run this after every
   `python pipeline.py` to refresh Supabase; it does not sync itself.
5. Copy `dashboard/.env.example` to `dashboard/.env` and fill in the same
   `SUPABASE_URL` but the **anon/public key** this time (Project Settings >
   API > `anon` `public`), not the service_role key from step 3.
6. `pip install -r dashboard/requirements.txt && streamlit run dashboard/app.py`

The sidebar tells you which source is active. If Supabase is configured
but a table comes back empty (e.g. you haven't synced yet), the dashboard
falls back to the local CSV for that section rather than showing nothing.

### Deploying to Streamlit Community Cloud

Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` under the app's Settings >
Secrets instead of a `.env` file — `data_loader.py` checks
`st.secrets` first. Point the app at `dashboard/app.py` as the entry file.

## Why the anon key here and the service_role key only in `supabase/`

`sync_to_supabase.py` runs on your own machine and needs to *write*, so it
uses the service_role key, which bypasses Row Level Security. The
dashboard only ever *reads*, and may end up deployed somewhere public, so
it uses the anon key. Keep the service_role key out of `dashboard/` and
out of anything you deploy — see the comments in `supabase/.env.example`
and `dashboard/.env.example`.

## What this dashboard deliberately does not do

Same scope discipline as `api/README.md`: there is no per-product demand
prediction anywhere in this dashboard. The AI Forecast tab shows the real
**store-wide** revenue forecast from Project 1's Prophet model, checked
against actual revenue, and says so on-screen — this store has 7 real
orders across 275 products, nowhere near enough history for a per-SKU
forecast that wouldn't be fabricated precision. See `DATA_PROVENANCE.md`
at the project root for the full reasoning.

## Data freshness

Like the API, this dashboard reads a snapshot — either the CSVs as of the
last `pipeline.py` run, or Supabase as of the last `sync_to_supabase.py`
run (each `st.cache_data` call has a 5-minute TTL on top of that). Neither
path watches for live changes.
