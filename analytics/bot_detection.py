# ==
# bot_detection.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The "bot-adjusted conversion rate" shown in 03_funnel_analysis.py and
# on the dashboard used to be a heuristic buried inline in that one
# script. Pulling it into its own named, documented, importable module
# makes it a real, testable piece of the pipeline instead of a few
# lines that only make sense if you're reading 03 top to bottom.
#
# WHAT THIS ACTUALLY DETECTS, AND WHAT IT DELIBERATELY DOES NOT:
# Shopify's session-by-location export gives session COUNTS PER CITY —
# it does not include IP addresses or per-request timestamps. So a
# per-request method (e.g. "flag 5 checkout attempts in 1 second from
# the same IP") cannot be built on this data — there is no IP or
# timestamp column to run it against, and this module does not
# pretend otherwise.
#
# What IS real in this data: 38.7% of this store's sessions (269 of
# 695) come from six specific towns that host major cloud-platform
# data centres (Meta, Google, Amazon/Google). Real human visitors do
# not cluster in those towns — this is a documented pattern far more
# consistent with automated crawler/monitoring traffic than organic
# visits, so this module flags sessions from those towns as LIKELY
# bot traffic. That is the honest ceiling of what this module claims:
# a city-matching heuristic worth adjusting the conversion rate for,
# not a confirmed, request-level bot-detection system.
# ==

import pandas as pd

# Named and documented rather than a magic list — each entry is a real,
# publicly known data-centre location for the platform named.
DATA_CENTER_TOWNS = {
    "Prineville": "Meta data centre town (Oregon)",
    "The Dalles": "Google data centre town (Oregon)",
    "Council Bluffs": "Google data centre town (Iowa)",
    "Altoona": "Meta data centre town (Iowa)",
    "Boardman": "Amazon/Google data centre town (Oregon)",
    "Luleå": "Meta Node Pole data centre town (Sweden)",
}


def flag_bot_sessions(location: pd.DataFrame, total_sessions: int) -> dict:
    """Flags sessions from known data-centre towns as likely non-human
    traffic and returns the figures needed to report a bot-adjusted
    conversion rate.

    Parameters
    ----------
    location : the already-loaded sessions_by_location.csv dataframe —
        must have 'Session city' and 'Sessions' columns.
    total_sessions : the real total session count (from
        visitors_over_time.csv), so the bot percentage is relative to
        the same total the rest of the funnel uses.

    Returns a dict with the flagged dataframe (adds a 'Likely Bot
    Traffic' column, doesn't mutate the input) plus bot_sessions,
    bot_pct, and adjusted_sessions — no order or revenue figures are
    touched here, this is a traffic-quality flag only.
    """
    flagged = location.copy()
    flagged["Likely Bot Traffic"] = flagged["Session city"].isin(DATA_CENTER_TOWNS.keys())

    bot_sessions = int(flagged.loc[flagged["Likely Bot Traffic"], "Sessions"].sum())
    bot_pct = round(bot_sessions / total_sessions * 100, 1) if total_sessions else 0.0
    adjusted_sessions = total_sessions - bot_sessions

    return {
        "location_flagged": flagged,
        "bot_sessions": bot_sessions,
        "bot_pct": bot_pct,
        "adjusted_sessions": adjusted_sessions,
    }


if __name__ == "__main__":
    # Standalone run: the same report 03_funnel_analysis.py prints
    # inline, useful for checking this module on its own without
    # re-running the whole funnel script.
    location = pd.read_csv("../raw_data/sessions_by_location.csv")
    visitors = pd.read_csv("../raw_data/visitors_over_time.csv")
    total_sessions = int(visitors["Sessions"].sum())

    result = flag_bot_sessions(location, total_sessions)
    print(f"Total sessions                         : {total_sessions:,}")
    print(f"Sessions from known data-centre towns   : {result['bot_sessions']:,} ({result['bot_pct']}% of all sessions)")
    print(f"Estimated real human sessions           : {result['adjusted_sessions']:,}")
    print("\nTowns flagged and why:")
    for town, why in DATA_CENTER_TOWNS.items():
        print(f"  {town}: {why}")
    print(
        "\nNote: this is a city-matching heuristic based on Shopify's session-by-location "
        "export, not a per-request/IP bot-detection system — this dataset has no IP address "
        "or per-request timestamp columns to run that kind of check against."
    )
