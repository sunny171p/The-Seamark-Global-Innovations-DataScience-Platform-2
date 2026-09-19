# ==
# 04_forecast_vs_actual.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY I BUILT THIS:
# Project 1's whole forecasting stage was trained on almost no real
# sales history and produced a 90-day Prophet forecast starting
# 2026-08-05, worth being honest about testing rather than filing
# away and forgetting. Project 2 now has real orders covering part of
# that exact forecast window, so this is the actual accuracy check —
# not a hypothetical one.
#
# HOW THE COMPARISON IS MADE FAIR:
# Project 1's forecast file is one continuous daily series: 2026-03-20
# through 2026-08-04 is real order history (quiet days zero-filled so
# Prophet trains on a true daily average — see Project 1's
# sales_forecast.py), and 2026-08-05 onward is the genuine 90-day
# future forecast. Filtering to dates after Project 1's last real
# order (2026-08-04) isolates that future block honestly. An earlier
# version of this script instead took a fixed row count (iloc[11:],
# from when Project 1's history was only 11 sparse monthly rows) —
# that broke silently the moment Project 1's history was zero-filled
# to a 138-row daily series, which is exactly why a date-based cutoff
# is used now instead of a row count. This script then keeps only the
# days that fall inside Project 2's real order data window (2026-08-01
# to 2026-09-14) — comparing a forecast against actuals outside the
# period any real data exists for wouldn't mean anything.
#
# WHY THIS DOESN'T CLAIM A DEAD-STOCK OR STOCKOUT COUNT:
# No inventory-quantity export exists for this catalogue, so this
# script cannot say how many real units are sitting unsold or which
# SKU would run out first — that needs a Shopify Inventory report
# this project doesn't have. What it can do honestly is turn the
# already-computed revenue gap into a capital-exposure estimate using
# this catalogue's own verified average margin, with the assumption
# stated plainly rather than hidden inside a bigger-sounding number.
# ==

import pandas as pd

# Project 1's forecast, copied into this project's raw_data/ — see
# DATA_PROVENANCE.md for why this cross-project file exists and where
# it came from.
forecast = pd.read_csv('../raw_data/project1_sales_forecast_90days.csv')
orders = pd.read_csv('../cleaned_data/orders_clean.csv')
products = pd.read_csv('../cleaned_data/products_clean.csv')

forecast['ds'] = pd.to_datetime(forecast['ds'])
orders['Created at'] = pd.to_datetime(orders['Created at'], utc=True).dt.tz_localize(None)

# Isolate the genuinely-future forecast block (see comment above).
# Date-based cutoff, not a fixed row count: this used to be
# forecast_sorted.iloc[11:], which silently broke once Project 1's
# history block stopped being exactly 11 rows long.
PROJECT1_LAST_REAL_ORDER_DATE = pd.Timestamp('2026-08-04')
forecast_sorted = forecast.sort_values('ds').reset_index(drop=True)
future_forecast = forecast_sorted[
    forecast_sorted['ds'] > PROJECT1_LAST_REAL_ORDER_DATE
].reset_index(drop=True)

REAL_DATA_WINDOW_START = pd.Timestamp('2026-08-01')
REAL_DATA_WINDOW_END = pd.Timestamp('2026-09-14')

overlap = future_forecast[
    (future_forecast['ds'] >= REAL_DATA_WINDOW_START) &
    (future_forecast['ds'] <= REAL_DATA_WINDOW_END)
]

print(f"Forecast future block: {len(future_forecast)} days ({future_forecast['ds'].min().date()} to {future_forecast['ds'].max().date()})")
print(f"Real order data window: {REAL_DATA_WINDOW_START.date()} to {REAL_DATA_WINDOW_END.date()}")
print(f"Overlapping days available for comparison: {len(overlap)}")

predicted_total = round(overlap['yhat'].sum(), 2)
predicted_lower = round(overlap['yhat_lower'].sum(), 2)
predicted_upper = round(overlap['yhat_upper'].sum(), 2)
actual_total = round(orders['Total'].sum(), 2)

print(f"\nPredicted revenue for the overlapping {len(overlap)} days : £{predicted_total} "
      f"(range £{predicted_lower} to £{predicted_upper})")
print(f"Actual real revenue in the same window        : £{actual_total}")

error_gbp = round(predicted_total - actual_total, 2)
error_pct = round(error_gbp / actual_total * 100, 1) if actual_total else None
overprediction_multiple = round(predicted_total / actual_total, 1) if actual_total else None

# Direction-neutral: an earlier version of this always said "overshot",
# which was only ever true because of the forecast bug fixed upstream in
# Project 1. Now that the forecast is honest, say what actually happened.
if error_gbp > 0:
    print(f"\nForecast overshot actual revenue by £{error_gbp} ({error_pct}% over, "
          f"{overprediction_multiple}x actual)")
elif error_gbp < 0:
    print(f"\nForecast undershot actual revenue by £{abs(error_gbp)} "
          f"({abs(error_pct)}% under, {overprediction_multiple}x actual)")
else:
    print("\nForecast matched actual revenue exactly for this window.")


# --
# WHAT THIS ACTUALLY MEANS
# --
# Being direct about this rather than softening it, whichever way the
# number lands: Project 1's forecast was trained on very little genuine
# sales history (the store had close to zero real orders at the time),
# so however this comparison comes out, it reflects how much that model
# could realistically know about a newly-relaunched, still-small store's
# actual conversion — not a verdict decided in advance. This isn't a
# reason to hide the forecast — it's a real, useful finding for a data
# science portfolio: a model's accuracy has to be checked against
# reality once real data exists, and this project did that check rather
# than assuming the forecast was right and moving on.
# --

print("\n=== INTERPRETATION ===")
if error_gbp > 0:
    print("Project 1's pre-launch forecast overestimated real demand for this")
    print("window. Most likely cause: the model had very little real order")
    print("history to train on at the time, so it had nothing to learn actual")
    print("early-stage conversion rates from.")
    print("This is a genuine forecast-accuracy finding, not a data error to hide —")
    print("it shows why a forecast needs re-validation once real sales exist.")
elif error_gbp < 0:
    print("Project 1's pre-launch forecast underestimated real demand for this")
    print("window — actual sales came in higher than predicted. Most likely")
    print("cause: the model had very little real order history to train on at")
    print("the time, so it had no way to anticipate how demand would actually")
    print("pick up.")
    print("This is a genuine forecast-accuracy finding, not a data error to hide —")
    print("it shows why a forecast needs re-validation once real sales exist.")
else:
    print("Project 1's pre-launch forecast matched actual demand for this window")
    print("almost exactly — a genuinely strong result given how little real")
    print("order history the model had to train on at the time.")


# --
# WHAT THIS FORECAST GAP WOULD COST IN REAL CAPITAL — AND WHAT DATA
# WOULD BE NEEDED TO GO FURTHER
# --
# The honest limit first: this store's product export has no stock-
# on-hand or inventory-quantity field (checked — Variant Inventory
# Tracker and Variant Inventory Policy exist, a quantity count
# doesn't), so this script CANNOT tell you how many actual units are
# sitting unsold, or when a specific SKU would stock out. Claiming
# otherwise without that data would be exactly the kind of invented
# precision this project exists to avoid. A real "Shopify Inventory"
# export would be needed to go further than this.
#
# What CAN be done honestly with what exists: when the forecast
# OVERpredicted (error_gbp > 0), turn that £ revenue gap into a
# capital-exposure estimate using this catalogue's own real average
# margin. If procurement had trusted this forecast and bought stock
# sized to it, the COST side of that unsold gap — not the revenue
# side — is what would actually sit as dead capital. Approximating
# cost as revenue x (1 - average margin%) is a simplification (it
# assumes the overprediction gap has the same margin mix as the
# catalogue average, a stated assumption, not a hidden one), but it's
# grounded in this project's own already-verified Margin % figures,
# not an invented number. When the forecast instead UNDERpredicted
# (error_gbp < 0), the "dead capital" framing doesn't apply at all —
# there's no unsold stock to cost out, and this project has no
# inventory data to size an under-stocking risk either, so that case
# says so plainly instead of forcing a number.
# --

avg_margin_pct = round(products['Margin %'].dropna().mean(), 1)

print("\n=== CAPITAL-EXPOSURE ESTIMATE (NOT A LITERAL DEAD-STOCK COUNT) ===")
print("No stock-on-hand/inventory-quantity export exists for this catalogue,")
print("so this cannot state how many units would sit unsold or run out —")
print("that would need a Shopify Inventory report this project doesn't have.")

if error_gbp > 0:
    capital_at_risk_gbp = round(error_gbp * (1 - avg_margin_pct / 100), 2)
    print(f"\nCatalogue average margin (from verified Margin % on {products['Margin %'].notna().sum()} products): {avg_margin_pct}%")
    print(f"Revenue overprediction gap (already computed above)             : £{error_gbp}")
    print(f"Estimated capital exposure at cost, if stock had been bought to")
    print(f"match this forecast                                             : £{capital_at_risk_gbp}")
    print("(Assumption stated plainly: this treats the overpredicted revenue as")
    print(" having this catalogue's average margin mix — a simplification, not a")
    print(" claim about which specific SKUs would be affected.)")
elif error_gbp < 0:
    capital_at_risk_gbp = None
    print("\nThe forecast underpredicted actual revenue here, so a dead-stock/")
    print("overstock capital-exposure estimate doesn't apply — the risk in an")
    print("underprediction scenario would be under-stocking against real demand,")
    print("not tying up capital in unsold goods. This project has no inventory-")
    print(f"quantity data to size that risk either (catalogue average margin, for")
    print(f"reference: {avg_margin_pct}%, from {products['Margin %'].notna().sum()} products).")
else:
    capital_at_risk_gbp = 0.0
    print("\nForecast and actual revenue matched, so there is no overprediction or")
    print("underprediction gap to translate into a capital-exposure estimate.")


summary = pd.DataFrame([{
    'overlap_days': len(overlap),
    'predicted_total_gbp': predicted_total,
    'predicted_lower_gbp': predicted_lower,
    'predicted_upper_gbp': predicted_upper,
    'actual_total_gbp': actual_total,
    'error_gbp': error_gbp,
    'error_pct': error_pct,
    'overprediction_multiple': overprediction_multiple,
    'avg_margin_pct_used': avg_margin_pct,
    'capital_at_risk_gbp': capital_at_risk_gbp,
}])
summary.to_csv('../outputs/forecast_vs_actual_summary.csv', index=False)
print("\nSummary saved to outputs/forecast_vs_actual_summary.csv")
