# ==
# fold_webhook_events.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# webhook_listener.py lands every incoming order event as its own raw
# JSON file, untouched, under raw_data/webhook_events/orders/. This is
# the separate second step: it reads those landed files, turns each
# one into rows in the same shape refresh_raw_data.py already produces
# (one row per line item, matching raw_data/orders_export.csv's real
# header), appends them, and moves each source file into a processed/
# subfolder so it's never folded in twice.
#
# Kept as its own script, run separately from the listener, on
# purpose. The listener's only job is to receive and land events
# reliably, fast, with nothing that could make it crash or hang under
# a real webhook from Shopify. Transformation logic, which is where
# an actual bug is likely to show up (see webhook_listener.py's own
# note on this), belongs somewhere safe to fix and rerun without
# touching the thing actually listening for live traffic.
#
# USAGE:
#   python shopify_sync/fold_webhook_events.py
#
# Safe to run on a schedule (every few minutes, say) or by hand
# whenever you want newly landed events folded in. Running it with
# nothing new landed is a no-op.

import csv
import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVENTS_DIR = PROJECT_ROOT / "raw_data" / "webhook_events" / "orders"
PROCESSED_DIR = EVENTS_DIR / "processed"
ORDERS_CSV = PROJECT_ROOT / "raw_data" / "orders_export.csv"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Must match raw_data/orders_export.csv's real header exactly, this is
# the same manual-export shape refresh_raw_data.py already writes.
CSV_COLUMNS = [
    "Name", "Email", "Financial Status", "Created at", "Currency",
    "Subtotal", "Shipping", "Taxes", "Total", "Discount Code",
    "Discount Amount", "Billing Country", "Shipping Country",
    "Payment Method", "Source", "Risk Level",
    "Lineitem name", "Lineitem quantity", "Lineitem price", "Lineitem sku",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("fold_webhook_events")


def _money(order: dict, *keys, default="0.00") -> str:
    node = order
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return str(node)


def _order_json_to_rows(order: dict) -> list[dict]:
    """One dict per line item, matching CSV_COLUMNS. Uses an empty
    string, not a guess, for anything the payload doesn't actually
    contain, an empty cell is honest, a made-up one isn't.
    """
    billing_country = (order.get("billing_address") or {}).get("country", "")
    shipping_country = (order.get("shipping_address") or {}).get("country", "")
    payment_method = ", ".join(order.get("payment_gateway_names") or [])
    discount_codes = order.get("discount_codes") or []
    discount_code = discount_codes[0].get("code", "") if discount_codes else ""

    line_items = order.get("line_items") or []
    if not line_items:
        log.warning("Order %s has no line items in the webhook payload -- skipping",
                    order.get("name", "unknown"))
        return []

    rows = []
    for item in line_items:
        rows.append({
            "Name": order.get("name", ""),
            "Email": order.get("email", ""),
            "Financial Status": order.get("financial_status", ""),
            "Created at": order.get("created_at", ""),
            "Currency": order.get("currency", ""),
            "Subtotal": _money(order, "subtotal_price"),
            "Shipping": _money(order, "total_shipping_price_set", "shop_money", "amount"),
            "Taxes": _money(order, "total_tax"),
            "Total": _money(order, "total_price"),
            "Discount Code": discount_code,
            "Discount Amount": _money(order, "total_discounts"),
            "Billing Country": billing_country,
            "Shipping Country": shipping_country,
            "Payment Method": payment_method,
            "Source": order.get("source_name", ""),
            # Order risk isn't always present on the order payload itself,
            # Shopify exposes it through a separate Order Risk endpoint/
            # webhook in some API versions. Left blank rather than guessed.
            "Risk Level": order.get("risk_level", ""),
            "Lineitem name": item.get("name", ""),
            "Lineitem quantity": item.get("quantity", ""),
            "Lineitem price": item.get("price", ""),
            "Lineitem sku": item.get("sku", ""),
        })
    return rows


def _fold_from_supabase(log) -> int:
    """Reads unfolded rows from Supabase's webhook_events table -- the
    durable landing zone a Render-deployed listener writes to, since its
    local disk doesn't survive a restart (see supabase/schema.sql). Folds
    each one with the exact same _order_json_to_rows() transform the local
    path uses, appends to the same ORDERS_CSV, then marks each row folded
    in Supabase so it's never folded twice. Returns how many rows it added.
    """
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return 0

    try:
        from supabase import create_client
    except ImportError:
        log.warning("supabase package not installed -- skipping the Supabase fold step. "
                    "pip install supabase to enable it.")
        return 0

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    result = client.table("webhook_events").select("id, order_name, payload").eq("folded", False).execute()
    pending = result.data or []
    if not pending:
        log.info("No unfolded rows in Supabase's webhook_events table.")
        return 0

    new_rows = []
    folded_ids = []
    for record in pending:
        try:
            new_rows.extend(_order_json_to_rows(record["payload"]))
            folded_ids.append(record["id"])
        except Exception as exc:
            log.error("Could not fold Supabase webhook_events row id=%s (%s): %s",
                      record.get("id"), record.get("order_name"), exc)

    if new_rows:
        write_header = not ORDERS_CSV.exists()
        with ORDERS_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            for row in new_rows:
                writer.writerow(row)

    if folded_ids:
        from datetime import datetime, timezone
        client.table("webhook_events").update({
            "folded": True,
            "folded_at": datetime.now(timezone.utc).isoformat(),
        }).in_("id", folded_ids).execute()

    log.info("Folded %d row(s) from %d Supabase event(s) into %s",
              len(new_rows), len(folded_ids), ORDERS_CSV.name)
    return len(new_rows)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    supabase_rows = _fold_from_supabase(log)

    if not EVENTS_DIR.exists():
        log.info("No raw_data/webhook_events/orders/ folder yet -- nothing local to fold.")
        pending = []
    else:
        pending = sorted(p for p in EVENTS_DIR.glob("*.json") if p.is_file())

    if not pending:
        log.info("Nothing new to fold in from local files.")
        if supabase_rows == 0:
            log.info("Nothing new from Supabase either -- nothing to do this run.")
        return

    if not ORDERS_CSV.exists():
        log.error("%s doesn't exist yet -- run refresh_raw_data.py once first "
                   "so this has a file with the right header to append to.", ORDERS_CSV)
        return

    import json

    new_rows = []
    for path in pending:
        try:
            order = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("Could not parse %s: %s -- leaving it in place, not marking processed", path.name, exc)
            continue
        new_rows.extend(_order_json_to_rows(order))
        path.rename(PROCESSED_DIR / path.name)

    if not new_rows:
        log.info("Folded 0 rows (files were empty or unparseable, none moved).")
        return

    with ORDERS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        for row in new_rows:
            writer.writerow(row)

    log.info("Appended %d row(s) from %d event file(s) to %s",
              len(new_rows), len(pending), ORDERS_CSV.name)
    log.info("Re-run `python pipeline.py` to fold these into cleaned_data/ and outputs/.")


if __name__ == "__main__":
    main()
