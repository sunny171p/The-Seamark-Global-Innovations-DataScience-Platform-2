# ==
# 07_affiliate_analysis.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY THIS EXISTS:
# Every earlier stage in this project works from Shopify's own data.
# UpPromote is a separate system this project hadn't looked at yet —
# it's where Seamark's affiliate programme actually lives, and
# DATA_PROVENANCE.md has flagged a "Known gap" about it since Stage 1
# was written: the export lists who has signed up, not which (if any)
# of the store's 7 real orders came through one of them. This stage
# doesn't try to close that gap by guessing — UpPromote's own export
# has no order-reference column, so there is nothing here to join
# against orders_clean.csv. What it DOES do is turn the raw signup
# list into the same kind of honest, recomputable summary every other
# stage produces, instead of leaving it as an unopened spreadsheet.
#
# WHAT THIS IS NOT:
# Not an attribution report. "Active" here means UpPromote's own
# programme status for that affiliate, not "drove a sale" — this
# script never states or implies a revenue figure for the affiliate
# channel, because the data to support one doesn't exist yet. See the
# "Known gap" section of DATA_PROVENANCE.md for the full reasoning and
# what a real closing of this gap would require (an UpPromote
# referral/commission report, not this signup export).
# ==

import pandas as pd

affiliates = pd.read_excel('../raw_data/uppromote_affiliates.xlsx')

print(f"=== AFFILIATE PROGRAMME SIGNUPS (UpPromote export, {len(affiliates)} rows) ===")

status_counts = affiliates['status'].fillna('Unknown').value_counts()
print("\nStatus breakdown:")
for status, count in status_counts.items():
    print(f"  {status:<10} {count}")

active_count = int((affiliates['status'] == 'Active').sum())
pending_count = int((affiliates['status'] == 'Pending').sum())
inactive_count = int((affiliates['status'] == 'Inactive').sum())
verified_count = int((affiliates['verified'] == 'yes').sum())
with_referral_link = int(affiliates['referral_link'].notna().sum())
never_logged_in = int((affiliates['login_count'].fillna(0) == 0).sum())
country_known = int(affiliates['country'].notna().sum())

print(f"\nVerified (UpPromote 'verified' flag): {verified_count} of {len(affiliates)}")
print(f"Have a working referral link         : {with_referral_link} of {len(affiliates)}")
print(f"Country recorded                     : {country_known} of {len(affiliates)}")
print(f"Never logged in since signup          : {never_logged_in} of {len(affiliates)}")


# --
# STEP 1 — WHAT THIS DATA ACTUALLY SUPPORTS SAYING
# --
# Being as direct here as every other stage: this is an engagement
# read on the programme, not a performance read. A high never-logged-in
# count is a genuine, actionable finding on its own (an affiliate who
# never logs in isn't sharing their link), independent of whether any
# of them drove a sale — which this data cannot show either way.
# --

print("\n=== HONEST READ ===")
print(f"{active_count} of {len(affiliates)} signups are Active in UpPromote, "
      f"{pending_count} Pending, {inactive_count} Inactive.")
if never_logged_in:
    print(f"{never_logged_in} of {len(affiliates)} affiliates have never logged back in since "
          "signing up — a real engagement gap, worth following up on directly, "
          "independent of any sales question this data can't answer.")
print("This says nothing about whether any of the store's 7 real orders came through "
      "an affiliate link — UpPromote's signup export has no order-reference column to "
      "check that against. See DATA_PROVENANCE.md's 'Known gap' section.")


# --
# SAVE SUMMARY
# --

summary = pd.DataFrame([{
    'total_signups': len(affiliates),
    'active_count': active_count,
    'pending_count': pending_count,
    'inactive_count': inactive_count,
    'verified_count': verified_count,
    'with_referral_link_count': with_referral_link,
    'never_logged_in_count': never_logged_in,
    'country_known_count': country_known,
    'attribution_available': False,
    'attribution_gap_note': (
        "UpPromote export lists programme signups only, with no order-reference "
        "column — it cannot show whether any of the 7 real orders were "
        "affiliate-driven. See DATA_PROVENANCE.md 'Known gap'."
    ),
}])
summary.to_csv('../outputs/affiliate_summary.csv', index=False)

by_status = status_counts.rename_axis('status').reset_index(name='count')
by_status.to_csv('../outputs/affiliate_by_status.csv', index=False)

print("\nSaved to outputs/affiliate_summary.csv and outputs/affiliate_by_status.csv")
print("Ready for a real UpPromote referral/commission export to be added once one exists.")
