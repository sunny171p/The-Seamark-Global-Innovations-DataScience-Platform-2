-- ==
-- schema.sql
-- Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
-- Supabase table definitions for the Streamlit dashboard
-- ==
--
-- WHY THIS EXISTS:
-- The dashboard can read straight from the local CSVs in cleaned_data/ and
-- outputs/ with zero setup. Supabase is an OPTIONAL upgrade: it lets the
-- same numbers be queried from anywhere (not just this machine) and lets
-- other Seamark tools (Smart3PL Router, Control Center) read the same
-- source of truth. Nothing here invents new numbers — every column maps
-- directly to a column the pipeline already produced.
--
-- HOW TO USE:
-- Paste this whole file into the Supabase project's SQL editor and run it
-- once. Then run `python supabase/sync_to_supabase.py` to populate the
-- tables from the pipeline's real CSV outputs. Re-run the sync after every
-- `python pipeline.py` to keep Supabase current — like the API's README
-- says, nothing here watches the files for changes automatically.
-- ==

-- One row per product, combining the classification + pricing-integrity +
-- margin-anomaly signals the same way api/main.py's /products/<handle>
-- endpoint does, so the dashboard doesn't need three separate queries.
create table if not exists products (
    handle text primary key,
    title text,
    vendor text,
    type text,
    variant_price numeric,
    variant_compare_at_price numeric,
    cost_per_item numeric,
    shipping_destination text,
    status text,
    discount_pct numeric,
    margin_pct numeric,
    auto_category text,
    text_cluster integer,
    pricing_status text,
    margin_anomaly boolean default false,
    synced_at timestamptz default now()
);

-- Snapshot tables: each sync replaces the single row (or small row set)
-- with the latest pipeline output. Timestamped so the dashboard can show
-- "as of" and so nobody mistakes a stale row for a live feed.
create table if not exists funnel_summary (
    id bigint generated always as identity primary key,
    total_visitors integer,
    total_sessions integer,
    total_orders integer,
    conversion_rate_pct numeric,
    likely_bot_sessions integer,
    likely_bot_pct numeric,
    adjusted_sessions integer,
    adjusted_conversion_rate_pct numeric,
    gateway_variance_found boolean,
    channel_variance_found boolean,
    aov_gbp numeric,
    scenario_lift_pct numeric,
    scenario_additional_orders numeric,
    scenario_additional_revenue_gbp numeric,
    synced_at timestamptz default now()
);

create table if not exists forecast_summary (
    id bigint generated always as identity primary key,
    overlap_days integer,
    predicted_total_gbp numeric,
    predicted_lower_gbp numeric,
    predicted_upper_gbp numeric,
    actual_total_gbp numeric,
    error_gbp numeric,
    error_pct numeric,
    overprediction_multiple numeric,
    avg_margin_pct_used numeric,
    capital_at_risk_gbp numeric,
    scope text,
    why_not_per_product text,
    synced_at timestamptz default now()
);

create table if not exists omnichannel_summary (
    id bigint generated always as identity primary key,
    website_sessions integer,
    website_orders integer,
    website_conversion_rate_pct numeric,
    website_window text,
    google_shopping_clicks integer,
    google_shopping_purchases integer,
    google_shopping_window text,
    data_source_note text,
    synced_at timestamptz default now()
);

create table if not exists pricing_integrity_summary (
    id bigint generated always as identity primary key,
    products_checked integer,
    verified_real_discount_count integer,
    misleading_discount_count integer,
    no_discount_count integer,
    integrity_score_pct numeric,
    margin_anomaly_count integer,
    margin_anomaly_pct numeric,
    margin_anomaly_threshold_pct numeric,
    synced_at timestamptz default now()
);

-- Non-PII subset of the UpPromote affiliate export. Deliberately excludes
-- address, phone, payment_info, w9_form, internal_note and similar fields
-- that have no place in a business-metrics dashboard.
create table if not exists affiliates (
    affiliate_id bigint primary key,
    email text,
    first_name text,
    last_name text,
    country text,
    program text,
    status text,
    verified text,
    login_count integer,
    date_created text,
    signup_source text,
    synced_at timestamptz default now()
);

create table if not exists cluster_top_terms (
    cluster integer primary key,
    size integer,
    top_terms text,
    synced_at timestamptz default now()
);

-- Long/tidy form of outputs/category_by_country.csv, easier to chart in
-- Streamlit than the wide pivot the CSV ships as.
create table if not exists category_by_country (
    id bigint generated always as identity primary key,
    auto_category text,
    country text,
    product_count integer,
    synced_at timestamptz default now()
);

-- Signup/engagement snapshot from analytics/07_affiliate_analysis.py.
-- Deliberately has no order-attribution column — see that script's own
-- header comment and DATA_PROVENANCE.md's "Known gap" for why.
create table if not exists affiliate_summary (
    id bigint generated always as identity primary key,
    total_signups integer,
    active_count integer,
    pending_count integer,
    inactive_count integer,
    verified_count integer,
    with_referral_link_count integer,
    never_logged_in_count integer,
    country_known_count integer,
    attribution_available boolean default false,
    attribution_gap_note text,
    synced_at timestamptz default now()
);

create table if not exists affiliate_by_status (
    id bigint generated always as identity primary key,
    status text,
    count integer,
    synced_at timestamptz default now()
);

-- Launch-readiness snapshot from analytics/08_pipeline_health.py — whether
-- the pipeline's own structural invariants held on its last run.
create table if not exists pipeline_health_summary (
    id bigint generated always as identity primary key,
    products_row_count integer,
    orders_row_count integer,
    customers_row_count integer,
    pricing_integrity_score_pct numeric,
    checks_passed integer,
    checks_total integer,
    overall_status text,
    run_at text,
    synced_at timestamptz default now()
);

create table if not exists pipeline_health_checks (
    id bigint generated always as identity primary key,
    check_name text,
    passed boolean,
    detail text,
    synced_at timestamptz default now()
);

-- Real catalogue mix (share of the 275 real products per category) vs
-- real sales mix (share of real order revenue per category), both
-- Seamark's own data. From analytics/09_catalog_vs_sales_mix.py.
create table if not exists catalog_vs_sales_mix (
    id bigint generated always as identity primary key,
    auto_category text,
    catalog_product_count integer,
    catalog_pct numeric,
    real_sales_revenue_gbp numeric,
    real_sales_pct numeric,
    synced_at timestamptz default now()
);

-- Seamark's real sales mix vs the real order mix of the external Olist
-- Brazilian E-Commerce dataset (99,441 real orders, 2016-2018) — a
-- labelled external reference point, never blended into Seamark's own
-- numbers. From analytics/10_external_category_benchmark.py.
create table if not exists external_category_benchmark (
    id bigint generated always as identity primary key,
    auto_category text,
    seamark_real_sales_pct numeric,
    external_olist_revenue_pct numeric,
    synced_at timestamptz default now()
);

-- Row Level Security: left disabled by default because this is an internal
-- analytics store with no end-user auth in front of it yet. If this
-- Supabase project is ever shared beyond the team, enable RLS and add
-- policies before that happens — don't ship it open.
