# Data Provenance — Project 2 (Post-Launch)

This project uses real Shopify data from Seamark's relaunched store — the
catalogue that replaced the one Project 1's pricing-integrity finding helped
retire. Every file below was checked against at least one other source before
being trusted; nothing here was loaded and used on faith.

## Files used

| File | Source | Verified against |
|---
| `raw_data/products_export.csv` | Shopify products export (native format), 6,250 rows / 275 unique products | Row count matches an earlier export of the same catalogue taken two weeks apart — this is a refresh, not new products |
| `raw_data/orders_export.csv` | Shopify orders export (native format), 11 line-item rows / 7 real orders | Order total (£417.27) matches `customers_export.csv`'s independent Total Spent sum exactly |
| `raw_data/customers_export.csv` | Shopify customers export (native format), 17 customers | Total Spent sum (£417.27) and Total Orders sum (7) both match `orders_export.csv` |
| `raw_data/total_sales_over_time.csv`, `total_sales_by_product.csv`, `visitors_over_time.csv`, `sessions_by_device_type.csv`, `sessions_by_referrer.csv`, `sessions_by_location.csv` | Shopify Analytics native exports, 2026-08-01 to 2026-09-14 | Order/revenue figures cross-check against `orders_export.csv` |
| `raw_data/uppromote_affiliates.xlsx` | UpPromote affiliate signup export, 14 affiliates | Used as-is — see "Known gap" below |
| `raw_data/merchant_center_observation.csv` | **Not a native export** — 7 figures read manually off the live Google Merchant Center dashboard (Analytics > Summary and Products > Traffic screens) on 2026-09-15, because no CSV export was found on either screen | Numbers transcribed exactly as Merchant Center displayed them, including Merchant Center's own "<20" impressions display — not rounded or estimated further |
| `raw_data/external_olist/olist_orders_dataset.csv`, `olist_order_items_dataset.csv`, `olist_products_dataset.csv`, `product_category_name_translation.csv` | **External, not Seamark's own data** — the Olist Brazilian E-Commerce Public Dataset (Kaggle: `olistbr/brazilian-ecommerce`), downloaded by Sunday Azeez. 99,441 real orders, 112,650 real order line items, Sep 2016–Oct 2018 | Row counts and structure match this dataset's own published documentation; used only for `10_external_category_benchmark.py`, a labelled external comparison — never blended into or used to adjust any of Seamark's own real numbers |

## Live data (not a dated export) — stock_alerts/

Every file in the table above is a static export someone pulled on a
specific date, which is why this document can say when it was pulled
and what it was checked against. `stock_alerts/check_stock.py` is
different on purpose: it calls Shopify's live Admin API each time it
runs and reports real, current inventory quantities — not a snapshot.
It's kept out of `pipeline.py` and out of the table above for exactly
that reason: nothing else in this project depends on a live network
call or a Shopify API credential, and this document can't give this
data a "pulled on" date the way it can for everything else, because a
new one exists every time it runs. `outputs/stock_check.csv` (read by
the dashboard's Stock Alerts section) carries its own
`checked_at_utc` timestamp per run instead — see
`stock_alerts/README.md` for full setup and honesty notes, including
why some products are reported as "not tracked" rather than guessed at.

## Data explicitly NOT used, and why

An earlier batch of three files (`seamark-visitor-analytics-r7c5.csv`,
`seamark-customers-h5q9.csv`, `seamark-abandoned-checkouts-t2k8.csv`) was
supplied before the files above and was excluded from this project. That
batch used a non-native, already-summarised CSV format and contained three
different, mutually contradictory order counts (7, 5, and 4) and two
different session-count totals (1,090 vs 754) across the same small set of
files — including one file contradicting itself internally. Rather than
guess which number was right, this project waited for the native Shopify
exports listed above, which fully reconcile with each other. If a native,
internally-consistent abandoned-checkout export becomes available later, it
can be added the same way.

## Cross-project file

`raw_data/project1_sales_forecast_90days.csv` is a direct copy of
`Seamark_DataScience_Project/outputs/sales_forecast_90days.csv` from Project 1,
used by `04_forecast_vs_actual.py` to check that forecast against Project 2's
real order data. It is not a new export — it's the same forecast file Project
1 already produced and documented, brought in here specifically to be tested
against reality.

## Known gap

The UpPromote export lists who has signed up as an affiliate, not which (if
any) of the 7 real orders were attributed to one. `07_affiliate_analysis.py`
(added after this section was first written) turns that signup list into a
real summary — status breakdown, verification, engagement (login activity)
— but it's still a signup/engagement read, not an attribution report, and
its own output says so explicitly (`attribution_available: false` in
`outputs/affiliate_summary.csv`, and the same field on the API's
`GET /affiliates/summary`). A referral/commission report from UpPromote
would close this gap — until then, this project states that the affiliate
programme is active without claiming any specific order was or wasn't
affiliate-driven.



## Country dimension

Unlike Project 1's catalogue, this one carries a `Shipping Destination`
metafield per product (UK / Nigeria / USA / Worldwide / Egypt),
reflecting the new store's organisation by category *and* country. This is
new ground Project 1 never had data for, and `02_product_classification.py`
produces a category-by-destination breakdown as a result.

## Methodology notes for the advanced-analytics stages

Four stages were extended to use less basic methods. Each addition was
scoped to what the real data can actually support  noted here so the
boundary is explicit, not buried in code comments only.

- **Product clustering (`02`)**: clusters are built from product TEXT
  (Title + Type + Tags) via TF-IDF and K-Means — 275 real products is
  enough rows for this.

- **Funnel friction (`03`)**: the real per-order `Payment Method` and
  `Source` columns were checked directly before claiming any
  gateway/channel friction point. All 7 orders used Shopify Payments via
  web — no variance exists in this data, and the script says so rather
  than inventing a finding. The "+5% conversion" figure is a labelled
  what-if scenario built on this store's real AOV and conversion rate, not
  a prediction.

- **Forecast capital exposure (`04`)**: no inventory-quantity export
  exists for this catalogue, so no dead-stock or stockout count is
  claimed anywhere in this project. The capital-exposure estimate applies
  this catalogue's own verified average margin to the already-computed
  revenue gap, with that assumption stated in the script's own output.

- **Margin anomaly detection (`05`)**: uses the IQR method against this
  catalogue's own margin distribution (not a fixed external threshold),
  run as part of the batch pipeline — never described as real-time, since
  it runs against a CSV export, not a live feed.

## Stages added after the original six (`07`–`10`)

- **Affiliate programme analysis (`07`)**: see "Known gap" above — this is
  a real summary of UpPromote's own signup export, not an attribution
  report, and its output says so in a machine-readable field
  (`attribution_available`), not just in prose.

- **Pipeline health check (`08`)**: re-checks a handful of the same
  structural invariants `tests/` checks (no duplicate product handles,
  every expected output file present and non-empty, headline totals
  agreeing with each other) as part of every normal `python pipeline.py`
  run, and fails the pipeline run itself (non-zero exit) if one breaks.
  This is a lighter, always-on companion to the real test suite, not a
  replacement for running `pytest` before an actual release.

- **Catalogue mix vs real sales mix (`09_catalog_vs_sales_mix.py`)**:
  compares this store's real catalogue mix (share of the 275 real
  products per category) against its real sales mix (share of real order
  revenue per category, from all 11 real line items). Both sides are
  Seamark's own real data  see that script's header comment for how
  each real line item is matched to a real product (SKU first, exact
  title as fallback; 11 of 11 matched).

- **External category benchmark (`10_external_category_benchmark.py`)**:
  compares Seamark's real sales mix against the real order mix of the
  external Olist dataset described above, mapped conservatively onto
  Seamark's 14 categories (an unmatched Olist category becomes "Other"
  rather than being force-fit see that script's header comment for the
  full mapping and reasoning). This is a reference point against one
  large, real, unrelated business explicitly not a prediction, and
  never used to adjust the AI Forecast or any other Seamark number.
