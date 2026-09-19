# Shopify Sync — refresh raw_data/ from the live API

Pulls fresh **products**, **orders**, and **customers** straight from
Shopify's Admin API and overwrites `raw_data/products_export.csv`,
`raw_data/orders_export.csv`, and `raw_data/customers_export.csv` — the
same three files you'd otherwise get by manually exporting from the
Shopify admin. Same underlying source (your live store), just automated.

## What this does NOT cover

Shopify's Analytics reports (`sessions_by_device_type.csv`,
`sessions_by_location.csv`, `sessions_by_referrer.csv`,
`visitors_over_time.csv`, `total_sales_by_product.csv`,
`total_sales_over_time.csv`) aren't available through the same Admin API
this script uses — those still need a manual export from Shopify's
Analytics section. Same goes for `raw_data/merchant_center_observation.csv`
(Google Merchant Center) and `raw_data/uppromote_affiliates.xlsx`
(UpPromote) — different services, different APIs, not built yet.

## Being upfront about testing

Every other live-data script in this project (`stock_alerts/check_stock.py`)
was verified against a real store before being called done. This one
was written against Shopify's documented Admin GraphQL API schema
without a live store to test it on — your first real run is the actual
test. If it fails, the error message names the exact field Shopify
rejected (see "If a field errors" below) — that's a small fix, not a
sign the whole thing is broken.

## Setup

### 1. Shopify Admin API access

This needs the same Shopify custom app as `stock_alerts/`, but with more
scopes ticked, since it also reads orders and customers:

- `read_products`
- `read_orders`
- `read_customers`

If you already made the custom app for `stock_alerts/`:
Shopify admin → Settings → Apps and sales channels → Develop apps → your
app → Configuration → tick the three scopes above (in addition to
whatever `stock_alerts/` already has) → Save → reinstall the app.

If you don't have the custom app yet, see `stock_alerts/README.md` for
the full walkthrough of creating one from scratch — same process, just
tick all six scopes (three from that guide plus the three above) in one
go instead of doing it twice.

**Two different credential shapes, depending on how Shopify set up your
app:**

- Some custom apps show a permanent Admin API access token starting with
  `shpat_` directly on the API credentials page — if yours does, that's
  all you need. Put it in `SHOPIFY_ADMIN_API_ACCESS_TOKEN` in `.env`.
- Apps created through Shopify's newer Dev Dashboard instead show a
  **Client ID** and a **Secret** (starting with `shpss_`) — no permanent
  token is shown at all. That's not a mistake or the wrong field; it's
  just how Shopify issues credentials for this app type now. In that
  case, leave `SHOPIFY_ADMIN_API_ACCESS_TOKEN` blank and fill in
  `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` instead — the script
  exchanges those for a real access token itself, automatically, every
  time it runs (that exchanged token only lasts 24 hours, so it can't be
  saved once and reused the way `shpat_` can).

Either way, if you ever add scopes and reinstall the app, Shopify issues
new credentials and the old ones stop working — update `stock_alerts/.env`
too if it's using credentials from the same app.

### 2. Cost per item (optional, for Margin %)

Reading `Cost per item` needs Shopify's "view product costs" permission
in addition to `read_products`. If your token doesn't have it, this
script doesn't fail — it just retries without that field and leaves
`Cost per item` blank, same as it would be missing from a manual export
for the same reason.

### 3. Environment file

```
cd shopify_sync
copy .env.example .env
```

Fill in `SHOPIFY_STORE_DOMAIN`, plus either `SHOPIFY_ADMIN_API_ACCESS_TOKEN`
or `SHOPIFY_CLIENT_ID` + `SHOPIFY_CLIENT_SECRET` — see whichever one your
app's credentials page actually shows you, explained above in step 1.

## Running it

```
pip install -r requirements.txt
python refresh_raw_data.py
```

Then, from the project root:

```
python pipeline.py
```

(and `python supabase/sync_to_supabase.py` afterwards, if you're using
the Supabase-hosted dashboard — this script only refreshes `raw_data/`,
nothing downstream updates on its own.)

## If a field errors

Shopify's GraphQL Admin API changes shape slightly between API versions.
If a run fails with an error naming a specific field (for example
`riskAssessment` or `discountApplications`), that field's exact shape
differs on your store's API version. Two options:

1. Open Shopify's GraphQL Admin API explorer (from your custom app's
   page, there's usually a "GraphiQL" link, or use
   `https://shopify.dev/docs/api/admin-graphql` to browse the current
   schema for your `SHOPIFY_API_VERSION`) and check the correct field
   shape, then update the query in `refresh_raw_data.py` to match.
2. For Risk Level specifically, this script already retries the whole
   orders fetch without `riskAssessment` if that field errors — so a
   `riskAssessment` error should self-recover and just leave `Risk Level`
   blank in the output, not stop the sync. If it's still stopping the
   sync, that's worth a closer look, not something to paper over.

## What "one row per product" means here

Shopify's manual CSV export has one row per product *variant/image*, with
most fields blank on every row except the first. This script writes one
row per product instead, using each product's first variant for price and
cost — `01_data_cleaning.py` only ever reads product-level fields anyway
(see its own header comment), so this is the same information the
pipeline actually uses, without the blank continuation rows a manual
export has to filter out first.

## The other way to get data in: webhooks instead of pulling

Everything above is a pull, you run this script and it asks Shopify for
a fresh snapshot. `webhook_listener.py`, in this same folder, is the
opposite: Shopify pushes an order to it the moment one actually happens,
instead of waiting to be asked. It lands each event as raw JSON under
`raw_data/webhook_events/`, and `fold_webhook_events.py` is the separate
step that turns those into rows appended to `orders_export.csv`. Full
setup, including how to verify the request actually came from Shopify
and how to expose this to the internet for testing, is documented at the
top of `webhook_listener.py` itself. Worth being honest about where this
stands: it's a real, runnable starting point built from Shopify's
documented webhook format, not something that's been checked against a
live webhook from this actual store yet, so test it with Shopify's own
"send test notification" button before trusting it with real traffic.
