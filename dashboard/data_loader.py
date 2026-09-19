# ==
# data_loader.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The dashboard should work the moment someone clones this repo, before
# they've ever touched Supabase — so this module tries Supabase first (if
# credentials are present) and falls back to reading the pipeline's own
# CSV outputs directly. Either path returns the exact same shape of data,
# so app.py never has to know or care which source it came from. This is
# the same "don't invent a number you don't have" discipline as the rest
# of Project 2: if a table/file is missing, the corresponding value comes
# back as an empty DataFrame or None, and app.py is responsible for saying
# so on-screen rather than pretending the section is empty because that's
# a valid state.
# ==

import os
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DATA_DIR = PROJECT_ROOT / "cleaned_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _get_secret(name: str):
    """Reads config from Streamlit secrets first (the normal way to deploy
    this on Streamlit Community Cloud), then falls back to a plain env var
    (the normal way to run it locally)."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def get_data_source() -> str:
    """Returns 'supabase' if usable credentials are configured, else
    'local_csv'. Only the anon/public key belongs here — this is the
    read-only client the deployed dashboard uses, never the service_role
    key that supabase/sync_to_supabase.py uses to write."""
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_ANON_KEY") or _get_secret("SUPABASE_KEY")
    if url and key:
        try:
            import supabase  # noqa: F401
            return "supabase"
        except ImportError:
            return "local_csv"
    return "local_csv"


@st.cache_resource
def _supabase_client():
    from supabase import create_client
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_ANON_KEY") or _get_secret("SUPABASE_KEY")
    return create_client(url, key)


def _from_supabase(table: str) -> pd.DataFrame:
    client = _supabase_client()
    resp = client.table(table).select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


def _read_csv_safe(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _read_excel_safe(path: Path) -> pd.DataFrame:
    return pd.read_excel(path) if path.exists() else pd.DataFrame()


@st.cache_data(ttl=300)
def load_products() -> pd.DataFrame:
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("products")
        if not df.empty:
            return df

    products = _read_csv_safe(CLEANED_DATA_DIR / "products_clean.csv")
    if products.empty:
        return products

    pricing = _read_csv_safe(OUTPUTS_DIR / "pricing_integrity_check.csv")
    anomaly = _read_csv_safe(OUTPUTS_DIR / "margin_anomaly_check.csv")
    anomaly_handles = set(anomaly["Handle"]) if not anomaly.empty else set()

    merged = products.merge(
        pricing[["Handle", "Pricing Status"]] if not pricing.empty else pd.DataFrame(columns=["Handle", "Pricing Status"]),
        on="Handle",
        how="left",
    )
    merged["margin_anomaly"] = merged["Handle"].isin(anomaly_handles)

    return pd.DataFrame({
        "handle": merged["Handle"],
        "title": merged["Title"],
        "vendor": merged.get("Vendor"),
        "type": merged.get("Type"),
        "variant_price": merged["Variant Price"],
        "variant_compare_at_price": merged.get("Variant Compare At Price"),
        "cost_per_item": merged.get("Cost per item"),
        "shipping_destination": merged.get("Shipping Destination"),
        "status": merged.get("Status"),
        "discount_pct": merged.get("Discount %"),
        "margin_pct": merged.get("Margin %"),
        "auto_category": merged.get("Auto_Category"),
        "text_cluster": merged.get("Text_Cluster"),
        "pricing_status": merged.get("Pricing Status"),
        "margin_anomaly": merged["margin_anomaly"],
    })


@st.cache_data(ttl=300)
def load_snapshot(table: str, csv_filename: str) -> dict:
    """Returns the single current-run row as a dict, or {} if unavailable."""
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase(table)
        if not df.empty:
            return df.iloc[-1].to_dict()

    df = _read_csv_safe(OUTPUTS_DIR / csv_filename)
    return df.iloc[0].to_dict() if not df.empty else {}


@st.cache_data(ttl=300)
def load_affiliates() -> pd.DataFrame:
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("affiliates")
        if not df.empty:
            return df

    df = _read_excel_safe(RAW_DATA_DIR / "uppromote_affiliates.xlsx")
    if df.empty:
        return df
    return pd.DataFrame({
        "affiliate_id": df["id"],
        "email": df["email"],
        "first_name": df["first_name"],
        "last_name": df["last_name"],
        "country": df.get("country"),
        "program": df.get("program"),
        "status": df.get("status"),
        "verified": df.get("verified"),
        "login_count": df.get("login_count"),
        "date_created": df.get("date_created"),
        "signup_source": df.get("signup_source"),
    })


@st.cache_data(ttl=300)
def load_affiliate_by_status() -> pd.DataFrame:
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("affiliate_by_status")
        if not df.empty:
            return df
    return _read_csv_safe(OUTPUTS_DIR / "affiliate_by_status.csv")


@st.cache_data(ttl=300)
def load_pipeline_health_checks() -> pd.DataFrame:
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("pipeline_health_checks")
        if not df.empty:
            return df
    return _read_csv_safe(OUTPUTS_DIR / "pipeline_health_checks.csv")


@st.cache_data(ttl=300)
def load_cluster_terms() -> pd.DataFrame:
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("cluster_top_terms")
        if not df.empty:
            return df.sort_values("cluster")
    return _read_csv_safe(OUTPUTS_DIR / "cluster_top_terms.csv")


@st.cache_data(ttl=300)
def load_category_by_country() -> pd.DataFrame:
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("category_by_country")
        if not df.empty:
            return df

    wide = _read_csv_safe(OUTPUTS_DIR / "category_by_country.csv")
    if wide.empty:
        return wide
    long_df = wide.melt(id_vars="Auto_Category", var_name="country", value_name="product_count")
    return long_df[long_df["product_count"] > 0].rename(columns={"Auto_Category": "auto_category"})


@st.cache_data(ttl=300)
def load_catalog_vs_sales_mix() -> pd.DataFrame:
    """From 09_catalog_vs_sales_mix.py — real catalogue mix (what share
    of the 275 products sit in each category) vs real sales mix (what
    share of real order revenue each category actually earned). Both
    sides are real data; nothing here is simulated.
    """
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("catalog_vs_sales_mix")
        if not df.empty:
            return df
    return _read_csv_safe(OUTPUTS_DIR / "catalog_vs_sales_mix.csv")


@st.cache_data(ttl=300)
def load_external_category_benchmark() -> pd.DataFrame:
    """From 10_external_category_benchmark.py — Seamark's real sales mix
    vs the real order mix of the Olist Brazilian E-Commerce dataset
    (99,441 real orders, 2016-2018). An external reference point, not a
    prediction — see that script's header comment for the full honesty
    rationale and the category-mapping caveats.
    """
    source = get_data_source()
    if source == "supabase":
        df = _from_supabase("external_category_benchmark")
        if not df.empty:
            return df
    return _read_csv_safe(OUTPUTS_DIR / "external_category_benchmark.csv")


@st.cache_data(ttl=300)
def load_stock_check() -> pd.DataFrame:
    """From stock_alerts/check_stock.py — real, live inventory pulled
    straight from Shopify's Admin API, not a dated CSV export. Unlike
    every other loader in this file, this one deliberately has no
    Supabase path: stock_alerts/ is a separate, opt-in add-on that
    isn't part of pipeline.py or sync_to_supabase.py, so there's
    nothing for a Supabase-hosted deployment to have synced. Empty
    means the add-on hasn't been set up or run yet, not that stock is
    empty — app.py is responsible for saying so on-screen.
    """
    return _read_csv_safe(OUTPUTS_DIR / "stock_check.csv")
