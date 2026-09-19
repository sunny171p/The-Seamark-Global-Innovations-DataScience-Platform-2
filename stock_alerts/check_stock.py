# ==
# check_stock.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Stock Alerts add-on
# ==
#
# WHY THIS LIVES OUTSIDE pipeline.py:
# Every stage in analytics/ reads a static CSV someone downloaded by
# hand — that's why DATA_PROVENANCE.md can say exactly when each file
# was pulled and verify it against another source. This script is
# different on purpose: it calls Shopify's live Admin API every time
# it runs, so what it reports is only ever "as of right now", not a
# dated snapshot. Keeping it out of pipeline.py keeps that distinction
# honest — running `python pipeline.py` never silently hits the
# network or depends on a Shopify API credential being present.
#
# WHAT THIS DOES:
# Pulls the real, current inventory quantity for every Shopify-tracked
# product variant straight from the live store via the Admin API,
# flags anything at 0 or below as out of stock, saves the result to
# outputs/stock_check.csv, and sends an email + a Windows desktop
# notification either way — a notification also fires on a clean run,
# it just says so, so a silent script never gets mistaken for a
# working one.
#
# WHAT IT DELIBERATELY DOES NOT DO:
# If a variant isn't Shopify-tracked (its inventory item has
# tracked: false), Shopify itself isn't enforcing a stock count for
# it, so this script reports "not tracked" rather than guessing
# whether it's out of stock — the same "don't invent a number you
# don't have" rule the rest of this project follows.
#
# HOW TO RUN IT:
#   One-off / manual : python check_stock.py
#   Weekly, automatic : see README.md in this folder for the one-time
#                        Windows Task Scheduler command that runs
#                        weekly_check.bat on a schedule.
#
# SETUP:
#   Copy .env.example to .env in this folder and fill in real values
#   first — see README.md for exactly how to get a Shopify Admin API
#   token and an email app password. Nothing here works without them,
#   and it will tell you clearly which one is missing rather than
#   failing with a confusing error.
# ==

import os
import sys
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DATA_DIR = PROJECT_ROOT / "cleaned_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ADMIN_API_ACCESS_TOKEN = os.environ.get("SHOPIFY_ADMIN_API_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07")

ALERT_EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO")
ALERT_EMAIL_APP_PASSWORD = os.environ.get("ALERT_EMAIL_APP_PASSWORD")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def fetch_live_inventory() -> pd.DataFrame:
    """Pages through every product via Shopify's GraphQL Admin API and
    returns one row per product Handle with its real, current total
    inventory quantity, summed across all of that product's
    Shopify-tracked variants. Handle is the same identifier Shopify
    uses in the CSV export this project's other stages already read,
    so no separate SKU-matching step is needed to join the two."""
    if not SHOPIFY_STORE_DOMAIN or not SHOPIFY_ADMIN_API_ACCESS_TOKEN:
        _fail(
            "SHOPIFY_STORE_DOMAIN / SHOPIFY_ADMIN_API_ACCESS_TOKEN not set. "
            "Copy stock_alerts/.env.example to stock_alerts/.env and fill them in — see README.md."
        )

    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ADMIN_API_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }

    query = """
    query ($cursor: String) {
      products(first: 100, after: $cursor) {
        pageInfo { hasNextPage }
        edges {
          cursor
          node {
            handle
            title
            variants(first: 100) {
              edges {
                node {
                  sku
                  inventoryQuantity
                  inventoryItem { tracked }
                }
              }
            }
          }
        }
      }
    }
    """

    rows = []
    cursor = None
    while True:
        resp = requests.post(
            url, headers=headers,
            json={"query": query, "variables": {"cursor": cursor}},
            timeout=30,
        )
        if resp.status_code != 200:
            _fail(
                f"Shopify API returned HTTP {resp.status_code}: {resp.text[:300]}\n"
                f"If this says 'Unsupported API version', edit SHOPIFY_API_VERSION in "
                f".env to a version Shopify's docs currently list."
            )
        payload = resp.json()
        if "errors" in payload:
            _fail(f"Shopify API returned errors: {payload['errors']}")

        products = payload["data"]["products"]
        for edge in products["edges"]:
            node = edge["node"]
            variants = [v["node"] for v in node["variants"]["edges"]]
            tracked_variants = [v for v in variants if v["inventoryItem"]["tracked"]]
            if tracked_variants:
                total_qty = sum(v["inventoryQuantity"] or 0 for v in tracked_variants)
                is_tracked = True
            else:
                total_qty = None
                is_tracked = False
            rows.append({
                "handle": node["handle"],
                "tracked": is_tracked,
                "live_inventory_qty": total_qty,
            })
            cursor = edge["cursor"]

        if not products["pageInfo"]["hasNextPage"]:
            break

    return pd.DataFrame(rows)


def send_email(subject: str, body: str) -> bool:
    if not (ALERT_EMAIL_FROM and ALERT_EMAIL_TO and ALERT_EMAIL_APP_PASSWORD):
        print("  SKIP email — ALERT_EMAIL_* not fully set in stock_alerts/.env.")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = ALERT_EMAIL_FROM
    msg["To"] = ALERT_EMAIL_TO
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(ALERT_EMAIL_FROM, ALERT_EMAIL_APP_PASSWORD)
            server.sendmail(ALERT_EMAIL_FROM, [ALERT_EMAIL_TO], msg.as_string())
        print(f"  Email sent to {ALERT_EMAIL_TO}")
        return True
    except Exception as e:
        print(f"  FAILED to send email: {e}")
        return False


def send_desktop_notification(title: str, message: str) -> bool:
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="Seamark Stock Alerts", timeout=15)
        print("  Desktop notification sent.")
        return True
    except Exception as e:
        print(f"  SKIP desktop notification — {e}")
        return False


def main() -> None:
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print("=" * 62)
    print("  Seamark stock check — live Shopify Admin API")
    print(f"  Run at: {run_at} (UTC)")
    print("=" * 62)

    live = fetch_live_inventory()
    print(f"  Pulled live inventory for {len(live)} products.")

    products_path = CLEANED_DATA_DIR / "products_clean.csv"
    if not products_path.exists():
        _fail(f"{products_path} not found — run `python pipeline.py` from the project root first.")
    products = pd.read_csv(products_path)

    merged = products[["Handle", "Title", "Auto_Category"]].merge(
        live, left_on="Handle", right_on="handle", how="left"
    )

    def _status(row):
        if pd.isna(row["tracked"]) or not row["tracked"]:
            return "not tracked"
        return "out of stock" if row["live_inventory_qty"] <= 0 else "in stock"

    merged["stock_status"] = merged.apply(_status, axis=1)
    merged["checked_at_utc"] = run_at

    out = merged[["Handle", "Title", "Auto_Category", "live_inventory_qty", "stock_status", "checked_at_utc"]]
    out.to_csv(OUTPUTS_DIR / "stock_check.csv", index=False)

    out_of_stock = out[out["stock_status"] == "out of stock"]
    not_tracked = out[out["stock_status"] == "not tracked"]
    in_stock = out[out["stock_status"] == "in stock"]

    print(f"  In stock     : {len(in_stock)}")
    print(f"  Out of stock : {len(out_of_stock)}")
    print(f"  Not tracked  : {len(not_tracked)} (Shopify isn't tracking a quantity for these)")

    if len(out_of_stock):
        names = "\n".join(f"  - {r.Title} ({r.Auto_Category})" for r in out_of_stock.itertuples())
        send_email(
            f"Seamark stock alert: {len(out_of_stock)} product(s) out of stock",
            f"Checked at {run_at} (UTC), live from Shopify.\n\n"
            f"{len(out_of_stock)} product(s) are at 0 stock:\n\n{names}\n\n"
            f"Full detail: outputs/stock_check.csv",
        )
        send_desktop_notification(
            "Seamark: products out of stock",
            f"{len(out_of_stock)} product(s) at 0 stock — check your email or outputs/stock_check.csv.",
        )
    else:
        send_email(
            "Seamark stock check: all clear",
            f"Checked at {run_at} (UTC). All {len(in_stock)} tracked products have stock. "
            f"{len(not_tracked)} product(s) aren't Shopify-tracked.",
        )
        send_desktop_notification(
            "Seamark: stock check complete",
            f"All {len(in_stock)} tracked products in stock.",
        )

    print("\n  Saved to outputs/stock_check.csv")
    print("=" * 62)


if __name__ == "__main__":
    main()
