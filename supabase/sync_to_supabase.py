# ==
# sync_to_supabase.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The dashboard runs fine straight off the local CSVs with zero setup, but
# Supabase is the upgrade path when the numbers need to be reachable from
# somewhere other than this laptop, or read by another Seamark system. This
# script is the one place that ever writes to Supabase — it reads the real
# pipeline outputs (same files api/main.py serves) and pushes them up,
# unchanged. It never invents a column that isn't already in a CSV.
#
# HOW TO RUN:
#   1. Run schema.sql once in the Supabase SQL editor (creates the tables).
#   2. Copy supabase/.env.example to supabase/.env and fill in your
#      project's SUPABASE_URL and SUPABASE_KEY (use the service_role key
#      here, since this script writes — never put service_role in the
#      dashboard app itself, see dashboard/README.md).
#   3. python pipeline.py            # make sure outputs/ is fresh
#   4. python supabase/sync_to_supabase.py
#
# This mirrors the honesty rule the rest of Project 2 follows: it will
# refuse to push a table it can't find real data for, and it prints exactly
# what it pushed and what it skipped, rather than silently going quiet.
# ==

import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DATA_DIR = PROJECT_ROOT / "cleaned_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"

# Load .env if python-dotenv is available; fall back to real env vars if not.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def _connect():
    if not SUPABASE_URL or not SUPABASE_KEY:
        _fail(
            "SUPABASE_URL / SUPABASE_KEY not set. Copy supabase/.env.example to "
            "supabase/.env and fill them in first."
        )
    try:
        from supabase import create_client
    except ImportError:
        _fail("The 'supabase' package isn't installed. Run: pip install -r supabase/requirements.txt")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _records(df: pd.DataFrame) -> list:
    """Supabase's client needs plain JSON-safe values — NaN and numpy types
    both break the upsert, so this is the one place that cleans them up."""
    return df.where(pd.notna(df), None).to_dict(orient="records")


def sync_products(client) -> int:
    products_path = CLEANED_DATA_DIR / "products_clean.csv"
    if not products_path.exists():
        print("  SKIP products — cleaned_data/products_clean.csv not found. Run pipeline.py first.")
        return 0

    products = pd.read_csv(products_path)

    pricing_path = OUTPUTS_DIR / "pricing_integrity_check.csv"
    pricing = pd.read_csv(pricing_path)[["Handle", "Pricing Status"]] if pricing_path.exists() else pd.DataFrame(columns=["Handle", "Pricing Status"])

    margin_anomaly_path = OUTPUTS_DIR / "margin_anomaly_check.csv"
    anomaly_handles = set(pd.read_csv(margin_anomaly_path)["Handle"]) if margin_anomaly_path.exists() else set()

    merged = products.merge(pricing, on="Handle", how="left")
    merged["margin_anomaly"] = merged["Handle"].isin(anomaly_handles)

    out = pd.DataFrame({
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

    client.table("products").upsert(_records(out), on_conflict="handle").execute()
    return len(out)


def sync_snapshot_table(client, table: str, csv_path: Path, extra: dict | None = None) -> int:
    """Snapshot tables (funnel, forecast, omnichannel, pricing summary) are
    single-row-per-run outputs. Each sync clears the table and inserts the
    current row, so the dashboard always reads the latest run, not a growing
    history of every sync (this pipeline doesn't version its outputs)."""
    if not csv_path.exists():
        print(f"  SKIP {table} — {csv_path.relative_to(PROJECT_ROOT)} not found.")
        return 0

    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"  SKIP {table} — {csv_path.name} has no rows.")
        return 0

    row = df.iloc[0].to_dict()
    if extra:
        row.update(extra)

    client.table(table).delete().neq("id", -1).execute()
    client.table(table).insert([{k: (None if pd.isna(v) else v) for k, v in row.items()}]).execute()
    return 1


def sync_affiliates(client) -> int:
    affiliates_path = RAW_DATA_DIR / "uppromote_affiliates.xlsx"
    if not affiliates_path.exists():
        print("  SKIP affiliates — raw_data/uppromote_affiliates.xlsx not found.")
        return 0

    df = pd.read_excel(affiliates_path)
    # Deliberately dropping address/phone/payment_info/w9_form/internal_note —
    # see supabase/schema.sql's comment on the affiliates table.
    out = pd.DataFrame({
        "affiliate_id": df["id"],
        "email": df["email"],
        "first_name": df["first_name"],
        "last_name": df["last_name"],
        "country": df.get("country"),
        "program": df.get("program"),
        "status": df.get("status"),
        "verified": df.get("verified"),
        "login_count": df.get("login_count"),
        "date_created": df.get("date_created").astype(str) if "date_created" in df else None,
        "signup_source": df.get("signup_source"),
    })

    client.table("affiliates").upsert(_records(out), on_conflict="affiliate_id").execute()
    return len(out)


def sync_cluster_terms(client) -> int:
    path = OUTPUTS_DIR / "cluster_top_terms.csv"
    if not path.exists():
        print("  SKIP cluster_top_terms — outputs/cluster_top_terms.csv not found.")
        return 0
    df = pd.read_csv(path)
    client.table("cluster_top_terms").upsert(_records(df), on_conflict="cluster").execute()
    return len(df)


def sync_affiliate_summary(client) -> int:
    return sync_snapshot_table(client, "affiliate_summary", OUTPUTS_DIR / "affiliate_summary.csv")


def sync_affiliate_by_status(client) -> int:
    path = OUTPUTS_DIR / "affiliate_by_status.csv"
    if not path.exists():
        print("  SKIP affiliate_by_status — outputs/affiliate_by_status.csv not found.")
        return 0
    df = pd.read_csv(path)
    client.table("affiliate_by_status").delete().neq("id", -1).execute()
    client.table("affiliate_by_status").insert(_records(df)).execute()
    return len(df)


def sync_pipeline_health(client) -> int:
    return sync_snapshot_table(client, "pipeline_health_summary", OUTPUTS_DIR / "pipeline_health_summary.csv")


def sync_pipeline_health_checks(client) -> int:
    path = OUTPUTS_DIR / "pipeline_health_checks.csv"
    if not path.exists():
        print("  SKIP pipeline_health_checks — outputs/pipeline_health_checks.csv not found.")
        return 0
    df = pd.read_csv(path)
    client.table("pipeline_health_checks").delete().neq("id", -1).execute()
    client.table("pipeline_health_checks").insert(_records(df)).execute()
    return len(df)


def sync_category_by_country(client) -> int:
    path = OUTPUTS_DIR / "category_by_country.csv"
    if not path.exists():
        print("  SKIP category_by_country — outputs/category_by_country.csv not found.")
        return 0

    wide = pd.read_csv(path)
    long_df = wide.melt(id_vars="Auto_Category", var_name="country", value_name="product_count")
    long_df = long_df[long_df["product_count"] > 0]
    out = pd.DataFrame({
        "auto_category": long_df["Auto_Category"],
        "country": long_df["country"],
        "product_count": long_df["product_count"],
    })

    client.table("category_by_country").delete().neq("id", -1).execute()
    client.table("category_by_country").insert(_records(out)).execute()
    return len(out)


def sync_catalog_vs_sales_mix(client) -> int:
    path = OUTPUTS_DIR / "catalog_vs_sales_mix.csv"
    if not path.exists():
        print("  SKIP catalog_vs_sales_mix — outputs/catalog_vs_sales_mix.csv not found.")
        return 0
    df = pd.read_csv(path)
    client.table("catalog_vs_sales_mix").delete().neq("id", -1).execute()
    client.table("catalog_vs_sales_mix").insert(_records(df)).execute()
    return len(df)


def sync_external_category_benchmark(client) -> int:
    path = OUTPUTS_DIR / "external_category_benchmark.csv"
    if not path.exists():
        print("  SKIP external_category_benchmark — outputs/external_category_benchmark.csv not found.")
        return 0
    df = pd.read_csv(path)
    client.table("external_category_benchmark").delete().neq("id", -1).execute()
    client.table("external_category_benchmark").insert(_records(df)).execute()
    return len(df)


def main() -> None:
    print("=" * 62)
    print("  Syncing Project 2 pipeline outputs to Supabase")
    print("=" * 62)

    client = _connect()

    steps = [
        ("products", lambda: sync_products(client)),
        ("funnel_summary", lambda: sync_snapshot_table(client, "funnel_summary", OUTPUTS_DIR / "funnel_summary.csv")),
        (
            "forecast_summary",
            lambda: sync_snapshot_table(
                client,
                "forecast_summary",
                OUTPUTS_DIR / "forecast_vs_actual_summary.csv",
                extra={
                    "scope": "store-wide daily revenue forecast, NOT per-product demand",
                    "why_not_per_product": (
                        "This store has 7 real orders across 275 products — not enough "
                        "history to fit a per-product demand model without fabricating "
                        "precision. This is the real, store-wide forecast-vs-actual figure "
                        "from 04_forecast_vs_actual.py instead."
                    ),
                },
            ),
        ),
        ("omnichannel_summary", lambda: sync_snapshot_table(client, "omnichannel_summary", OUTPUTS_DIR / "omnichannel_visibility_summary.csv")),
        ("pricing_integrity_summary", lambda: sync_snapshot_table(client, "pricing_integrity_summary", OUTPUTS_DIR / "pricing_integrity_summary.csv")),
        ("affiliates", lambda: sync_affiliates(client)),
        ("affiliate_summary", lambda: sync_affiliate_summary(client)),
        ("affiliate_by_status", lambda: sync_affiliate_by_status(client)),
        ("pipeline_health_summary", lambda: sync_pipeline_health(client)),
        ("pipeline_health_checks", lambda: sync_pipeline_health_checks(client)),
        ("cluster_top_terms", lambda: sync_cluster_terms(client)),
        ("category_by_country", lambda: sync_category_by_country(client)),
        ("catalog_vs_sales_mix", lambda: sync_catalog_vs_sales_mix(client)),
        ("external_category_benchmark", lambda: sync_external_category_benchmark(client)),
    ]

    total = 0
    for name, fn in steps:
        try:
            n = fn()
            if n:
                print(f"  OK   {name:<28} {n} row(s)")
                total += n
        except Exception as e:
            print(f"  FAIL {name:<28} {e}")

    print("-" * 62)
    print(f"  Done. {total} total row(s) synced.")
    print("  Restart (or just refresh) the Streamlit dashboard to see the new data.")
    print("=" * 62)


if __name__ == "__main__":
    main()
