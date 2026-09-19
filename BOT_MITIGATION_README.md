# The Seamark Global Innovations Project 2
# Author: Sunday Emmanuel Azeez

# Bot Traffic Mitigation — How This Project Handles It

## What the dashboard's "bot-adjusted conversion rate" actually is

`analytics/bot_detection.py` flags sessions from six towns that host major
cloud-platform data centres — Prineville and The Dalles (Oregon), Council
Bluffs and Altoona (Iowa), Boardman (Oregon), and Luleå (Sweden) — as
likely non-human traffic. That's **38.7% of this store's sessions (269 of
695)**. Real visitors don't cluster in those specific towns; it's a
pattern far more consistent with automated crawler or monitoring traffic
than organic visits.

Removing those sessions from the denominator changes the site-wide
conversion rate from **1.007%** (all sessions) to **1.643%**
(bot-adjusted, 426 estimated real sessions) — the figure the dashboard
leads with.

## What this method can and can't do

**Can do:** flag sessions by city, using Shopify's own
`sessions_by_location.csv` export, which reports session counts per city.

**Can't do:** flag individual bot *requests* — for example "5 checkout
attempts in 1 second from the same IP address." That would need IP
addresses and per-request timestamps, and Shopify's aggregate location
export doesn't include either. Building that check would mean inventing
data this store doesn't have, which this project deliberately avoids
everywhere else (see `DATA_PROVENANCE.md`).

## Why it lives in its own file

`analytics/bot_detection.py` used to be a few inline lines inside
`03_funnel_analysis.py`. It's now a separate, documented, importable
module with one function (`flag_bot_sessions`) so the detection logic is
a real, testable, reusable piece of the pipeline — not something you'd
only understand by reading through the funnel script line by line.

## If this store gets IP/timestamp-level data in future

A per-request method (rate-limiting by IP, or an anomaly model like
Isolation Forest over request timing) becomes possible once Shopify
Plus/checkout logs or a server-side event log with IP + timestamp exist.
Nothing in this project currently has access to that, so nothing here
claims to run that kind of check.
