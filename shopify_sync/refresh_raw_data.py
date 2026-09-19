# ==
# refresh_raw_data.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Shopify Sync add-on
# ==
#
# WHY THIS EXISTS:
# raw_data/products_export.csv, orders_export.csv and customers_export.csv
# have always been whatever you last exported by hand from the Shopify
# admin. This script gets the same three files the same way stock_alerts/
# gets live inventory — straight from Shopify's Admin API — so refreshing
# them doesn't mean opening the Shopify admin and clicking through three
# separate exports every time.
#
# WHAT THIS DOES NOT DO:
# It does not touch cleaned_data/, outputs/, or the dashboard. Run
# `python pipeline.py` afterwards to turn the fresh raw_data/ files into
# updated numbers — same two-step process as a manual export, just with
# the first step automated. It also does not touch
# raw_data/sessions_by_*.csv, visitors_over_time.csv, total_sales_*.csv,
# or the Google Merchant Center / UpPromote files — those come from
# Shopify's Analytics reports and other services this script doesn't talk
# to, and still need a manual export. See README.md for the full list of
# what is and isn't covered.
#
# WHY IT LIVES OUTSIDE pipeline.py, SAME REASONING AS stock_alerts/:
# `python pipeline.py` should never silently hit the network or need a
# Shopify credential just to re-analyse files that are already sitting on
# disk. Pulling fresh data is a separate, deliberate step you run first.
#
# BEING HONEST ABOUT WHAT'S NOT VERIFIED YET:
# Every other script in this project was tested against real data before
# being called done. This one hasn't been — it was written against
# Shopify's documented Admin GraphQL API schema without a live store to
# test it on. The Orders section in particular uses a couple of fields
# (riskAssessment, discountApplications) that are more likely than the
# rest to need a small fix depending on your store's exact API version.
# If a run fails, the error Shopify sends back will name the exact field
# it didn't like — see the "IF A FIELD ERRORS" note in README.md before
# assuming something is broken beyond a one-line fix.
#
# HOW TO RUN IT:
#   python refresh_raw_data.py
#   python ../pipeline.py          (from the project root, afterwards)
#
# SETUP:
#   Copy .env.example to .env in this folder and fill in real values —
#   see README.md for exactly which Shopify Admin API scopes this needs
#   (more than stock_alerts/ needs, since this also reads orders and
#   customers, not just inventory).
#
# ABOUT THE ACCESS TOKEN:
#   Shopify's newer "Dev Dashboard" custom apps don't hand you a
#   permanent token directly — they give you a Client ID + Client Secret,
#   and the script exchanges those for a real Admin API access token
#   itself, each run (that exchanged token only lasts 24 hours, so it
#   can't just be saved once and reused — see _get_access_token() below).
#   If your app DOES show a permanent token starting with shpat_, you can
#   use that directly instead — set SHOPIFY_ADMIN_API_ACCESS_TOKEN in
#   .env and the exchange step is skipped entirely.
# ==

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ADMIN_API_ACCESS_TOKEN = os.environ.get("SHOPIFY_ADMIN_API_ACCESS_TOKEN")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07")

SHIPPING_DEST_COL = "Shipping Destinations (product.metafields.custom.shipping_destinations)"


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Cache so a single run only exchanges Client ID/Secret for a token once,
# not once per GraphQL call (fetch_products/orders/customers each call
# _graphql() many times over pagination).
_access_token_cache = {"token": None}


def _get_access_token() -> str:
    # Preferred path: a permanent shpat_ token was set directly in .env —
    # use it as-is, no exchange needed.
    if SHOPIFY_ADMIN_API_ACCESS_TOKEN:
        return SHOPIFY_ADMIN_API_ACCESS_TOKEN

    if _access_token_cache["token"]:
        return _access_token_cache["token"]

    if not SHOPIFY_STORE_DOMAIN or not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
        _fail(
            "Need either SHOPIFY_ADMIN_API_ACCESS_TOKEN, or SHOPIFY_STORE_DOMAIN + "
            "SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET, set in shopify_sync/.env — see README.md."
        )

    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/oauth/access_token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": SHOPIFY_CLIENT_ID,
            "client_secret": SHOPIFY_CLIENT_SECRET,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        _fail(
            f"Couldn't exchange the Client ID/Secret for an access token — "
            f"HTTP {resp.status_code}: {resp.text[:500]}\n"
            f"Double-check SHOPIFY_STORE_DOMAIN, SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET in .env."
        )
    token = resp.json().get("access_token")
    if not token:
        _fail(f"Shopify's response didn't include an access_token: {resp.text[:500]}")

    _access_token_cache["token"] = token
    return token


# How many times _graphql() will wait and retry after Shopify throttles a
# request, before giving up and failing the sync for real. Shopify's
# GraphQL Admin API charges every query against a per-store cost budget
# that refills over time — this store's own sync barely touches that
# budget today (275 products, a handful of orders), but a bigger store
# syncing more often could genuinely hit it, and the old version of this
# script just died the first time that happened instead of waiting it out.
_MAX_THROTTLE_RETRIES = 5


def _is_throttled(payload: dict) -> bool:
    for err in payload.get("errors", []) or []:
        if (err.get("extensions") or {}).get("code") == "THROTTLED":
            return True
    return False


def _graphql(query: str, variables: dict) -> dict:
    if not SHOPIFY_STORE_DOMAIN:
        _fail(
            "SHOPIFY_STORE_DOMAIN not set. "
            "Copy shopify_sync/.env.example to shopify_sync/.env and fill it in — see README.md."
        )
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": _get_access_token(),
        "Content-Type": "application/json",
    }

    for attempt in range(1, _MAX_THROTTLE_RETRIES + 1):
        resp = requests.post(url, headers=headers, json={"query": query, "variables": variables}, timeout=30)

        # Shopify signals "slow down" two different ways: a plain HTTP 429
        # (rare on this endpoint, but worth defending against anyway), or an
        # ordinary HTTP 200 whose body contains a GraphQL error with
        # extensions.code == "THROTTLED" -- this is the normal case, since
        # Shopify's cost-based throttling happens inside an otherwise
        # successful request. Both get the same treatment: wait, then try
        # again, instead of failing the whole sync over a temporary limit.
        if resp.status_code == 429:
            wait_s = float(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"  Rate-limited (HTTP 429). Waiting {wait_s:.1f}s before retrying "
                  f"(attempt {attempt}/{_MAX_THROTTLE_RETRIES})...")
            time.sleep(wait_s)
            continue

        if resp.status_code != 200:
            _fail(
                f"Shopify API returned HTTP {resp.status_code}: {resp.text[:500]}\n"
                f"If this says 'Unsupported API version', edit SHOPIFY_API_VERSION in .env "
                f"to a version Shopify's docs currently list."
            )

        payload = resp.json()

        if _is_throttled(payload):
            # extensions.cost.throttleStatus.restoreRate is how fast this
            # store's query-cost budget refills, in points per second --
            # use it to wait roughly as long as it takes to earn this
            # query's cost back, and fall back to plain exponential backoff
            # if Shopify doesn't send that detail for some reason.
            cost = (payload.get("extensions") or {}).get("cost") or {}
            throttle_status = cost.get("throttleStatus") or {}
            restore_rate = throttle_status.get("restoreRate") or 0
            requested_cost = cost.get("requestedQueryCost") or 0
            wait_s = min(10.0, max(1.0, requested_cost / restore_rate)) if restore_rate else float(2 ** attempt)
            print(f"  Shopify throttled this request. Waiting {wait_s:.1f}s before retrying "
                  f"(attempt {attempt}/{_MAX_THROTTLE_RETRIES})...")
            time.sleep(wait_s)
            continue

        if "errors" in payload:
            _fail(
                f"Shopify API returned errors: {payload['errors']}\n"
                f"See README.md's 'IF A FIELD ERRORS' note — this usually names the exact "
                f"field to fix, not a sign the whole script is broken."
            )

        return payload["data"]

    _fail(
        f"Shopify kept throttling this request even after {_MAX_THROTTLE_RETRIES} retries. "
        f"Try again in a minute or two -- this usually just means a lot of sync traffic "
        f"happened at once, not that anything is broken."
    )


# --
# PRODUCTS
# --
# One row per VARIANT, matching Shopify's own manual CSV export shape —
# this matters because 09_catalog_vs_sales_mix.py matches real order line
# items to a product by Variant SKU, and an order can be for any variant
# of a product (a specific size/colour), not just the first one. Only the
# first variant row of each product has Handle/Title/Vendor/etc. filled
# in (every other row leaves those blank) — same as a real manual export,
# and 01_data_cleaning.py already expects exactly this shape (its own
# header comment says so): it keeps only the row where Title isn't blank,
# which is how it gets to one row per product.
#
# Fetches up to 100 variants per product — comfortably more than this
# catalogue actually has; if a product ever has more than that, only its
# first 100 variants' SKUs would be covered here.
# --

PRODUCTS_QUERY = """
query ($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage }
    edges {
      cursor
      node {
        handle
        title
        vendor
        productType
        tags
        status
        shippingDestinations: metafield(namespace: "custom", key: "shipping_destinations") { value }
        variants(first: 100) {
          edges {
            node {
              sku
              price
              compareAtPrice
              inventoryItem { unitCost { amount } }
            }
          }
        }
      }
    }
  }
}
"""

# Fallback used only if the store's API version / permissions reject
# inventoryItem.unitCost (needs Shopify's "view product costs" access on
# top of read_products) — same shape minus the cost field, so the sync
# still succeeds with Cost per item left blank rather than failing
# outright over one field it can't see.
PRODUCTS_QUERY_NO_COST = PRODUCTS_QUERY.replace(
    "inventoryItem { unitCost { amount } }", ""
)


def fetch_products() -> pd.DataFrame:
    rows = []
    cursor = None
    query = PRODUCTS_QUERY
    cost_available = True

    while True:
        try:
            data = _graphql(query, {"cursor": cursor})
        except SystemExit:
            if query is PRODUCTS_QUERY:
                print("  Cost per item isn't readable with this token/API version — "
                      "retrying without it (Margin % just won't be calculable).")
                query = PRODUCTS_QUERY_NO_COST
                cost_available = False
                cursor = None
                rows = []
                continue
            raise

        products = data["products"]
        for edge in products["edges"]:
            node = edge["node"]
            variants = node["variants"]["edges"]
            metafield = node.get("shippingDestinations")
            shipping_dest = metafield["value"] if metafield else None

            if not variants:
                # A product with no variants shouldn't happen in practice,
                # but skipping it silently would just make it vanish from
                # the export — write one row with blank variant fields
                # instead so it's still visible and countable.
                variants = [{"node": {}}]

            for i, v_edge in enumerate(variants):
                v = v_edge["node"]
                unit_cost = None
                if cost_available:
                    inv_item = v.get("inventoryItem") or {}
                    unit_cost_obj = inv_item.get("unitCost")
                    unit_cost = unit_cost_obj["amount"] if unit_cost_obj else None

                if i == 0:
                    # First variant row: carries the product-level fields,
                    # same as the first row of a product's group in a real
                    # manual export.
                    rows.append({
                        "Handle": node["handle"],
                        "Title": node["title"],
                        "Vendor": node["vendor"],
                        "Type": node["productType"],
                        "Tags": ", ".join(node["tags"]) if node["tags"] else "",
                        "Variant SKU": v.get("sku"),
                        "Variant Price": v.get("price"),
                        "Variant Compare At Price": v.get("compareAtPrice"),
                        "Cost per item": unit_cost,
                        SHIPPING_DEST_COL: shipping_dest,
                        "Status": (node["status"] or "").lower(),
                    })
                else:
                    # Continuation row for an additional variant — Handle
                    # is still filled in (it's what 09_catalog_vs_sales_mix.py
                    # ultimately maps a matched SKU back to), but the
                    # product-level fields are left blank, same as a real
                    # manual export leaves them blank on these rows. This
                    # is what lets 01_data_cleaning.py's existing "drop
                    # rows with a blank Title" logic keep exactly one row
                    # per product, unchanged.
                    rows.append({
                        "Handle": node["handle"],
                        "Title": None,
                        "Vendor": None,
                        "Type": None,
                        "Tags": None,
                        "Variant SKU": v.get("sku"),
                        "Variant Price": v.get("price"),
                        "Variant Compare At Price": v.get("compareAtPrice"),
                        "Cost per item": unit_cost,
                        SHIPPING_DEST_COL: None,
                        "Status": None,
                    })
            cursor = edge["cursor"]

        if not products["pageInfo"]["hasNextPage"]:
            break

    return pd.DataFrame(rows)


# --
# ORDERS
# --
# One row per LINE ITEM with the order-level fields repeated across every
# line item of that order — this matches the shape Shopify's own manual
# CSV export has, and the shape 01_data_cleaning.py expects (it collapses
# this back down itself via .groupby('Name').first()).
# --

ORDERS_QUERY = """
query ($cursor: String) {
  orders(first: 50, after: $cursor) {
    pageInfo { hasNextPage }
    edges {
      cursor
      node {
        name
        email
        displayFinancialStatus
        createdAt
        currencyCode
        subtotalPriceSet { shopMoney { amount } }
        totalShippingPriceSet { shopMoney { amount } }
        totalTaxSet { shopMoney { amount } }
        totalPriceSet { shopMoney { amount } }
        currentTotalDiscountsSet { shopMoney { amount } }
        discountApplications(first: 5) {
          edges {
            node {
              ... on DiscountCodeApplication { code }
            }
          }
        }
        billingAddress { countryCodeV2 }
        shippingAddress { countryCodeV2 }
        paymentGatewayNames
        sourceName
        riskAssessment: riskAssessment(first: 1) { assessments { riskLevel } }
        lineItems(first: 100) {
          edges {
            node {
              name
              quantity
              originalUnitPriceSet { shopMoney { amount } }
              sku
            }
          }
        }
      }
    }
  }
}
"""

# Fallback if riskAssessment's exact shape doesn't match this store's API
# version — Risk Level just comes back blank rather than failing the
# whole sync over a field this project only ever displays, never
# calculates from.
ORDERS_QUERY_NO_RISK = ORDERS_QUERY.replace(
    'riskAssessment: riskAssessment(first: 1) { assessments { riskLevel } }\n        ', ""
)


def _discount_code(node) -> str:
    for edge in node["discountApplications"]["edges"]:
        code = edge["node"].get("code")
        if code:
            return code
    return ""


def _risk_level(node) -> str:
    ra = node.get("riskAssessment")
    if not ra or not ra.get("assessments"):
        return ""
    return ra["assessments"][0].get("riskLevel", "") or ""


def fetch_orders() -> pd.DataFrame:
    rows = []
    cursor = None
    query = ORDERS_QUERY
    risk_available = True

    while True:
        try:
            data = _graphql(query, {"cursor": cursor})
        except SystemExit:
            if query is ORDERS_QUERY:
                print("  Risk assessment isn't readable with this token/API version — "
                      "retrying without it (Risk Level will just be blank).")
                query = ORDERS_QUERY_NO_RISK
                risk_available = False
                cursor = None
                rows = []
                continue
            raise

        orders = data["orders"]
        for edge in orders["edges"]:
            node = edge["node"]
            billing = node.get("billingAddress") or {}
            shipping = node.get("shippingAddress") or {}
            risk_level = _risk_level(node) if risk_available else ""

            line_items = node["lineItems"]["edges"]
            if not line_items:
                # An order with no line items shouldn't happen in practice,
                # but skipping it silently would just make the order vanish
                # from the export — write one row with blank line-item
                # fields instead so it's still visible and countable.
                line_items = [{"node": {"name": "", "quantity": None, "originalUnitPriceSet": {"shopMoney": {"amount": None}}, "sku": ""}}]

            for li_edge in line_items:
                li = li_edge["node"]
                rows.append({
                    "Name": node["name"],
                    "Email": node["email"],
                    "Financial Status": (node["displayFinancialStatus"] or "").lower(),
                    "Created at": node["createdAt"],
                    "Currency": node["currencyCode"],
                    "Subtotal": node["subtotalPriceSet"]["shopMoney"]["amount"],
                    "Shipping": node["totalShippingPriceSet"]["shopMoney"]["amount"],
                    "Taxes": node["totalTaxSet"]["shopMoney"]["amount"],
                    "Total": node["totalPriceSet"]["shopMoney"]["amount"],
                    "Discount Code": _discount_code(node),
                    "Discount Amount": node["currentTotalDiscountsSet"]["shopMoney"]["amount"],
                    "Billing Country": billing.get("countryCodeV2", ""),
                    "Shipping Country": shipping.get("countryCodeV2", ""),
                    "Payment Method": ", ".join(node.get("paymentGatewayNames") or []),
                    "Source": node.get("sourceName") or "",
                    "Risk Level": risk_level,
                    "Lineitem name": li["name"],
                    "Lineitem quantity": li["quantity"],
                    "Lineitem price": li["originalUnitPriceSet"]["shopMoney"]["amount"] if li.get("originalUnitPriceSet") else None,
                    "Lineitem sku": li.get("sku", ""),
                })
            cursor = edge["cursor"]

        if not orders["pageInfo"]["hasNextPage"]:
            break

    return pd.DataFrame(rows)


# --
# CUSTOMERS
# --

CUSTOMERS_QUERY = """
query ($cursor: String) {
  customers(first: 100, after: $cursor) {
    pageInfo { hasNextPage }
    edges {
      cursor
      node {
        id
        firstName
        lastName
        email
        defaultAddress { countryCodeV2 }
        amountSpent { amount }
        numberOfOrders
      }
    }
  }
}
"""


def fetch_customers() -> pd.DataFrame:
    rows = []
    cursor = None
    while True:
        data = _graphql(CUSTOMERS_QUERY, {"cursor": cursor})
        customers = data["customers"]
        for edge in customers["edges"]:
            node = edge["node"]
            default_addr = node.get("defaultAddress") or {}
            rows.append({
                "Customer ID": node["id"].rsplit("/", 1)[-1],
                "First Name": node.get("firstName") or "",
                "Last Name": node.get("lastName") or "",
                "Email": node.get("email") or "",
                "Default Address Country Code": default_addr.get("countryCodeV2", ""),
                "Total Spent": node["amountSpent"]["amount"] if node.get("amountSpent") else 0,
                "Total Orders": node.get("numberOfOrders") or 0,
            })
            cursor = edge["cursor"]
        if not customers["pageInfo"]["hasNextPage"]:
            break
    return pd.DataFrame(rows)


def main() -> None:
    print("=" * 62)
    print("  Seamark Shopify sync — refreshing raw_data/ from the live API")
    print("=" * 62)

    print("\nFetching products...")
    products = fetch_products()
    products.to_csv(RAW_DATA_DIR / "products_export.csv", index=False)
    print(f"  {len(products)} products saved to raw_data/products_export.csv")

    print("\nFetching orders (this can take a while on a store with many orders)...")
    orders = fetch_orders()
    orders.to_csv(RAW_DATA_DIR / "orders_export.csv", index=False)
    real_order_count = orders["Name"].nunique() if len(orders) else 0
    print(f"  {len(orders)} line-item rows across {real_order_count} orders saved to raw_data/orders_export.csv")

    print("\nFetching customers...")
    customers = fetch_customers()
    customers.to_csv(RAW_DATA_DIR / "customers_export.csv", index=False)
    print(f"  {len(customers)} customers saved to raw_data/customers_export.csv")

    print("\n" + "=" * 62)
    print("  DONE. This only refreshed raw_data/ — nothing else has changed yet.")
    print("  Next: run `python pipeline.py` from the project root to turn this")
    print("  into updated cleaned_data/ and outputs/, and (if you use it)")
    print("  `python supabase/sync_to_supabase.py` to push it to the hosted dashboard.")
    print("=" * 62)


if __name__ == "__main__":
    main()
