# ==
# 06_omnichannel_visibility.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY THIS EXISTS:
# Every earlier stage in this project analyses ONE source — Shopify's
# own exports. Shopify's own dashboard can't show you what happens
# before a visitor ever reaches your site — how visible your products
# are on Google Shopping's free listings, a completely separate
# channel Shopify has no data on at all. This stage blends that
# channel in, which is the genuine "gap Shopify misses" that a basic
# Shopify-only analytics setup can't show.
#
# WHAT THIS IS NOT:
# This is not a marketing-attribution or ROAS script. Seamark runs no
# paid ads (confirmed directly — no Meta Ads, no Google Ads spend
# exists), so there is no ad spend to attribute against, and this
# script makes no ROAS or ad-spend-saved claim. What it blends is two
# real, free channels: Shopify's own site traffic/orders, and Google
# Merchant Center's free organic Shopping-listing visibility.
#
# WHY THE MERCHANT CENTER DATA IS HANDLED DIFFERENTLY FROM EVERYTHING
# ELSE IN THIS PROJECT:
# Every other raw_data file here is a native export. Google Merchant
# Center's current UI did not expose a CSV export on the screens
# checked (Analytics > Summary, Products > Traffic) — confirmed by
# directly viewing the live dashboard, not assumed. So these seven
# numbers were read straight off the dashboard and recorded in
# raw_data/merchant_center_observation.csv, with the exact screen and
# date noted for each one. This is a real limitation, stated plainly
# rather than hidden behind a script that looks like it processed a
# clean export.
#
# THE TIME-WINDOW MISMATCH, STATED PLAINLY:
# Every other stage in this project compares the fixed window
# 2026-08-01 to 2026-09-14, because that's what the real order data
# covers. The Merchant Center numbers are Merchant Center's own
# rolling "Last 28 days" filter as viewed on 2026-09-15 (roughly
# 2026-08-18 to 2026-09-15) — a different, overlapping-but-not-
# identical window. This script does NOT pretend these line up
# exactly; it states both windows and treats the comparison as
# directionally informative, not a precise reconciliation.
# ==

import pandas as pd

funnel = pd.read_csv('../outputs/funnel_summary.csv').iloc[0]
merchant_center = pd.read_csv('../raw_data/merchant_center_observation.csv')

print("=== CHANNEL 1: SEAMARK'S OWN WEBSITE (SHOPIFY DATA, 2026-08-01 to 2026-09-14) ===")
print(f"Real sessions          : {int(funnel['total_sessions']):,}")
print(f"Real orders            : {int(funnel['total_orders'])}")
print(f"Conversion rate         : {funnel['conversion_rate_pct']}%")
print(f"Average order value     : £{funnel['aov_gbp']}")

print("\n=== CHANNEL 2: GOOGLE SHOPPING FREE LISTINGS (MERCHANT CENTER, ~last 28 days to 2026-09-15) ===")
print("(Manually read off the live Merchant Center dashboard — see raw_data/")
print(" merchant_center_observation.csv for exactly which screen each number")
print(" came from. No CSV export was available on these screens.)")
for _, row in merchant_center.iterrows():
    note = f"  ({row['notes']})" if pd.notna(row['notes']) and row['notes'] else ""
    print(f"  [{row['report_screen']} | {row['time_period_filter']}] {row['metric']}: {row['value']}{note}")


# --
# STEP 1 — WHAT THE TWO CHANNELS TOGETHER ACTUALLY SHOW
# --
# Being direct about what this comparison does and doesn't prove: it
# does NOT show that Google Shopping is "underperforming" against the
# website in a controlled sense — different window, different metric
# definitions, no shared identifier between the two data sources. What
# it DOES honestly show is that Seamark's real orders are currently
# coming entirely through the website channels this project has
# already measured (direct/social/search), and that the free Google
# Shopping channel — a channel this store has already set up and pays
# nothing extra for — isn't contributing any of that yet.
# --

gs_purchases = int(merchant_center.loc[merchant_center['metric'] == 'Organic - Purchases', 'value'].iloc[0])
gs_clicks = int(merchant_center.loc[merchant_center['metric'] == 'Ads + Organic - Clicks', 'value'].iloc[0])

print("\n=== WHAT THIS COMPARISON ACTUALLY SHOWS ===")
print(f"Real orders attributed to Google Shopping (from Merchant Center's own data): {gs_purchases}")
print(f"Real orders from the store's other channels (Shopify data, same rough period): {int(funnel['total_orders'])}")
print("\nHonest read: Google Shopping free listings are set up and technically")
print("active, but are generating close to zero visibility and zero orders so")
print("far. This is a genuine, actionable finding — an already-connected, no-cost")
print("channel with headroom to grow — not a channel that's failing after real")
print("investment, since nothing has been invested in it beyond enabling it.")


# --
# SAVE SUMMARY
# --

summary = pd.DataFrame([{
    'website_sessions': int(funnel['total_sessions']),
    'website_orders': int(funnel['total_orders']),
    'website_conversion_rate_pct': funnel['conversion_rate_pct'],
    'website_window': '2026-08-01 to 2026-09-14',
    'google_shopping_clicks': gs_clicks,
    'google_shopping_purchases': gs_purchases,
    'google_shopping_window': 'rolling last 28 days, observed 2026-09-15',
    'data_source_note': 'Google Shopping figures manually read from Merchant Center dashboard - no CSV export available',
}])
summary.to_csv('../outputs/omnichannel_visibility_summary.csv', index=False)
print("\nSummary saved to outputs/omnichannel_visibility_summary.csv")
print("Ready for GA4 traffic-acquisition data to be added once exported.")
