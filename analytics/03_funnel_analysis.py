# ==
# 03_funnel_analysis.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY I BUILT THIS:
# Project 1 could only ever show a hypothetical funnel — there were
# no real purchases to put at the bottom of it. This is the first
# time this business has a genuine visitor → session → order funnel,
# built entirely from real Shopify Analytics exports and the 7 real
# orders from 01_data_cleaning.py.
#
# WHAT I DELIBERATELY DID NOT DO:
# Shopify's aggregate session-by-device and session-by-referrer
# exports don't link individual sessions to individual orders — they
# only give site-wide totals per dimension. So this script does not
# claim "mobile converts at X%" or "Facebook traffic converts at Y%",
# because that data doesn't actually exist in these exports. What it
# can honestly report is the overall site-wide conversion rate, and
# the device/referrer mix of traffic, kept as two separate facts
# rather than forced into a false attribution.
#
# CHECKED FOR A GATEWAY/CHANNEL FRICTION POINT — DIDN'T FIND ONE:
# I checked the real per-ORDER Payment Method and Source columns
# (this data does exist at order level, unlike device/referrer). All
# 7 real orders used Shopify Payments via web. There's no gateway or
# channel variance in this data to analyse, so this script reports
# that honestly instead of manufacturing a friction-point finding
# that the store's own data doesn't support.
#
# THE "5% DROP-OFF IMPROVEMENT" SECTION IS A SCENARIO, NOT A FINDING:
# It takes this store's real average order value and real conversion
# rate and shows what a +5% relative improvement would be worth in
# pounds — useful for weighing "is fixing checkout friction worth
# it", but explicitly labelled as hypothetical, because nothing in
# this project actually delivered that improvement.
#
# THE BOT-TRAFFIC ADJUSTMENT:
# 38.7% of this store's sessions (269 of 695) come from towns known to
# host major cloud/social-platform data centres — Prineville and The
# Dalles OR, Council Bluffs and Altoona IA, Boardman OR, and Luleå,
# Sweden — a pattern far more consistent with automated crawler or
# link-preview traffic than real visitors clustering in those specific
# towns. Reporting the conversion rate on all 695 sessions without
# flagging this would understate how the site is actually performing
# with real human visitors, so this script reports both figures.
# ==

import pandas as pd

visitors = pd.read_csv('../raw_data/visitors_over_time.csv')
device = pd.read_csv('../raw_data/sessions_by_device_type.csv')
referrer = pd.read_csv('../raw_data/sessions_by_referrer.csv')
location = pd.read_csv('../raw_data/sessions_by_location.csv')
orders = pd.read_csv('../cleaned_data/orders_clean.csv')
raw_orders = pd.read_csv('../raw_data/orders_export.csv', low_memory=False)

total_sessions = int(visitors['Sessions'].sum())
total_visitors = int(visitors['Online store visitors'].sum())
total_orders = len(orders)

print(f"Total online store visitors : {total_visitors:,}")
print(f"Total sessions               : {total_sessions:,}")
print(f"Total real orders            : {total_orders}")


# --
# STEP 1 — OVERALL CONVERSION RATE
# --

conversion_rate = round(total_orders / total_sessions * 100, 3)
print(f"\nOverall conversion rate (orders / sessions): {conversion_rate}%")


# --
# STEP 2 — BOT/DATA-CENTRE TRAFFIC ADJUSTMENT
# --
# This used to be a heuristic inline in this script; it now lives in
# its own documented module (bot_detection.py) so it's a real, named,
# reusable piece of the pipeline rather than a few lines only this
# script knows about. See that file for exactly what it does and does
# not detect.
# --

from bot_detection import DATA_CENTER_TOWNS, flag_bot_sessions

_bot_result = flag_bot_sessions(location, total_sessions)
location = _bot_result['location_flagged']
bot_sessions = _bot_result['bot_sessions']
bot_pct = _bot_result['bot_pct']
adjusted_sessions = _bot_result['adjusted_sessions']
adjusted_conversion_rate = round(total_orders / adjusted_sessions * 100, 3) if adjusted_sessions else None

print(f"\nSessions from known data-centre towns : {bot_sessions:,} ({bot_pct}% of all sessions)")
print(f"Estimated real human sessions          : {adjusted_sessions:,}")
print(f"Conversion rate on likely-human sessions only: {adjusted_conversion_rate}%")
print("(This is an estimate based on session city matching known data-centre")
print(" locations, not a confirmed bot-detection system — flagged as a pattern")
print(" worth investigating further, not stated as certain.)")


# --
# STEP 3 — TRAFFIC MIX (reported separately from conversion — no
# session-to-order link exists in this data, so these are description,
# not attribution)
# --

print("\n=== SESSIONS BY DEVICE TYPE ===")
print(device[['Session device type', 'Sessions']].to_string(index=False))

print("\n=== TOP 10 REFERRER SOURCES BY SESSIONS ===")
top_referrers = referrer.groupby('Referrer source')['Sessions'].sum().sort_values(ascending=False).head(10)
print(top_referrers)


# --
# STEP 4 — CHECKING FOR A REAL GATEWAY/CHANNEL FRICTION POINT (NOT
# ASSUMING ONE EXISTS)
# --
# It's tempting to claim "checkout drops off at a specific payment
# gateway" or "a specific channel converts worse" — that's the kind
# of finding a portfolio piece likes to have. So this checks it
# against the real per-order Payment Method and Source columns in the
# raw order export, rather than asserting it without looking.
# --

order_level_raw = raw_orders.groupby('Name', as_index=False).first()
payment_method_counts = order_level_raw['Payment Method'].value_counts(dropna=True)
source_counts = order_level_raw['Source'].value_counts(dropna=True)

print("\n=== CHECKING FOR PAYMENT-GATEWAY / CHANNEL FRICTION (REAL ORDER DATA) ===")
print("Payment methods used across all real orders:")
print(payment_method_counts.to_string())
print("\nOrder source across all real orders:")
print(source_counts.to_string())

gateway_variance_found = len(payment_method_counts) > 1
channel_variance_found = len(source_counts) > 1

if not gateway_variance_found and not channel_variance_found:
    print("\nFinding: all 7 real orders used the same payment method")
    print(f"('{payment_method_counts.index[0]}') via the same source")
    print(f"('{source_counts.index[0]}'). There is no gateway or channel")
    print("variance in this data to analyse — ruling this out honestly")
    print("rather than inventing a friction point the data doesn't show.")
    print("This would become checkable again once the store processes")
    print("orders through more than one payment option or channel.")
else:
    print("\nVariance found — see counts above for where it concentrates.")


# --
# STEP 5 — WHAT A REAL DROP-OFF IMPROVEMENT WOULD BE WORTH
# --
# This is explicitly a SCENARIO, not a finding — this project has no
# lever it pulled to actually raise conversion by 5%, and says so.
# What it CAN do honestly is take the real bot-adjusted conversion
# rate and the real average order value and show, in real pounds,
# what a 5% RELATIVE improvement in that rate would be worth — so a
# conversation about "should we invest in fixing checkout friction"
# has an actual number to weigh against, drawn from this store's own
# figures rather than an industry rule of thumb.
# --

aov_gbp = round(orders['Total'].sum() / total_orders, 2) if total_orders else None

scenario_lift_pct = 5.0
scenario_new_rate = round(adjusted_conversion_rate * (1 + scenario_lift_pct / 100), 3) if adjusted_conversion_rate else None
scenario_additional_orders = None
scenario_additional_revenue_gbp = None

if adjusted_conversion_rate and adjusted_sessions and aov_gbp:
    scenario_additional_orders = round(
        adjusted_sessions * (scenario_new_rate - adjusted_conversion_rate) / 100, 2
    )
    scenario_additional_revenue_gbp = round(scenario_additional_orders * aov_gbp, 2)

print(f"\n=== SCENARIO: +{scenario_lift_pct}% RELATIVE CONVERSION IMPROVEMENT (HYPOTHETICAL) ===")
print(f"Real average order value                 : £{aov_gbp}")
print(f"Current bot-adjusted conversion rate      : {adjusted_conversion_rate}%")
print(f"Scenario conversion rate (+{scenario_lift_pct}% relative)   : {scenario_new_rate}%")
print(f"Additional orders over {adjusted_sessions:,} sessions      : {scenario_additional_orders}")
print(f"Additional revenue implied                : £{scenario_additional_revenue_gbp}")
print("(This is a what-if calculation on this store's own real AOV and")
print(" conversion rate — not a prediction that a specific fix delivers")
print(" exactly 5%. It exists to put a real £ figure next to the idea of")
print(" investing in checkout/friction improvements.)")


# --
# SAVE SUMMARY FOR THE DASHBOARD
# --

summary = pd.DataFrame([{
    'total_visitors': total_visitors,
    'total_sessions': total_sessions,
    'total_orders': total_orders,
    'conversion_rate_pct': conversion_rate,
    'likely_bot_sessions': bot_sessions,
    'likely_bot_pct': bot_pct,
    'adjusted_sessions': adjusted_sessions,
    'adjusted_conversion_rate_pct': adjusted_conversion_rate,
    'gateway_variance_found': gateway_variance_found,
    'channel_variance_found': channel_variance_found,
    'aov_gbp': aov_gbp,
    'scenario_lift_pct': scenario_lift_pct,
    'scenario_additional_orders': scenario_additional_orders,
    'scenario_additional_revenue_gbp': scenario_additional_revenue_gbp,
}])
summary.to_csv('../outputs/funnel_summary.csv', index=False)
print("\nSummary saved to outputs/funnel_summary.csv")
print("Ready for 04_forecast_vs_actual.py")
