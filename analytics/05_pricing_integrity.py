# ==
# 05_pricing_integrity.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY I BUILT THIS:
# Project 1 found that 259 of 271 products on the old catalogue had a
# misleading discount — a "was £X" price that was actually lower than
# or equal to the real selling price, so the discount badge was
# showing something untrue. That finding was part of why the old
# catalogue got deleted and relaunched. This script runs the exact
# same check against the new catalogue, because a finding like that
# only means something if you go back and check whether it actually
# got fixed, rather than assuming a relaunch solved it.
#
# THE RESULT, CHECKED NOT ASSUMED:
# It did get fixed. Every one of the 273 products with a Compare At
# Price set has a genuine discount — none where the selling price is
# higher than or equal to what it's being compared against. That's
# not a number I expected going in; it's what the same check Project
# 1 used says about this catalogue.
#
# ALSO IN THIS SCRIPT: MARGIN ANOMALY DETECTION
# A misleading-discount check only catches one kind of pricing
# problem. This script also runs an IQR-based statistical scan over
# real Margin % (computed in 01_data_cleaning.py) to flag products
# priced anomalously close to — or below — their cost, batch-run each
# time the pipeline runs, not claimed as a live/real-time system.
# ==

import pandas as pd

products = pd.read_csv('../cleaned_data/products_clean.csv')

checked = products[products['Variant Compare At Price'].notna()].copy()
print(f"Products with a Compare At Price set (checkable): {len(checked)} of {len(products)}")

checked['Pricing Status'] = checked.apply(
    lambda row: 'Misleading Discount' if row['Variant Price'] > row['Variant Compare At Price']
    else 'Verified Real Discount' if row['Variant Price'] < row['Variant Compare At Price']
    else 'No Discount (Same Price)',
    axis=1,
)

status_counts = checked['Pricing Status'].value_counts()
print("\n=== PRICING INTEGRITY CHECK (SAME METHOD AS PROJECT 1) ===")
print(status_counts)

misleading_count = int((checked['Pricing Status'] == 'Misleading Discount').sum())
verified_count = int((checked['Pricing Status'] == 'Verified Real Discount').sum())
integrity_score = round(verified_count / len(checked) * 100, 1) if len(checked) else 0.0

print(f"\nPricing integrity score (verified real discounts / all checked): {integrity_score}%")

if misleading_count == 0:
    print("\nNo misleading discounts found on the current catalogue — the pricing")
    print("problem Project 1 found on the old catalogue does not appear to have")
    print("carried over to the relaunch, based on this same check.")
else:
    print(f"\n{misleading_count} products still show a misleading discount — worth reviewing individually.")


# --
# SAVE FOR THE TRUST SCORE ENGINE
# --
# This is the per-product signal Seamark_Control_Center's
# trust_score_engine.py reads to build the customer-facing Trust
# Score — kept as a lookup by Handle so it can be joined onto any
# product easily.
# --

output = checked[['Handle', 'Title', 'Pricing Status']]
output.to_csv('../outputs/pricing_integrity_check.csv', index=False)

summary = pd.DataFrame([{
    'products_checked': len(checked),
    'verified_real_discount_count': verified_count,
    'misleading_discount_count': misleading_count,
    'no_discount_count': int((checked['Pricing Status'] == 'No Discount (Same Price)').sum()),
    'integrity_score_pct': integrity_score,
}])
summary.to_csv('../outputs/pricing_integrity_summary.csv', index=False)

print("\nSaved to outputs/pricing_integrity_check.csv and outputs/pricing_integrity_summary.csv")


# ==
# MARGIN ANOMALY DETECTION
# ==
# The check above catches one specific problem: a misleading discount
# badge. It doesn't catch a different, equally real problem — a
# product priced so close to its cost (or below it) that it's quietly
# losing money, whether from a typo, an outdated cost import, or an
# overlapping discount code stacking further than intended. This
# section catches that second problem, statistically, from the real
# Margin % this project already computed in 01_data_cleaning.py.
#
# METHOD, STATED PLAINLY:
# This uses the IQR (interquartile range) method — a standard,
# well-established outlier statistic, not a custom threshold picked
# to produce a nicer-looking result. A product is flagged if its
# margin falls more than 1.5x the IQR below the catalogue's own
# 25th-percentile margin. That threshold is DERIVED FROM THIS
# CATALOGUE'S OWN DISTRIBUTION, not a fixed "anything under 20%"
# rule — so it adapts to what's actually normal for this store rather
# than a number borrowed from somewhere else.
#
# WHY THIS IS NOT CALLED "REAL-TIME":
# This runs as part of the same batch pipeline as everything else in
# this project, against a CSV export — not a live feed. Calling it
# "real-time" would be exactly the kind of overclaim this project
# avoids. It's accurate to call it an automated anomaly scan that runs
# every time the pipeline runs, which is what it actually is.
# ==

margin_data = products[products['Margin %'].notna()].copy()

q1 = margin_data['Margin %'].quantile(0.25)
q3 = margin_data['Margin %'].quantile(0.75)
iqr = q3 - q1
lower_fence = q1 - 1.5 * iqr

margin_data['Margin Anomaly'] = margin_data['Margin %'] < lower_fence

anomaly_count = int(margin_data['Margin Anomaly'].sum())
anomaly_pct = round(anomaly_count / len(margin_data) * 100, 1) if len(margin_data) else 0.0

print(f"\n=== MARGIN ANOMALY DETECTION (IQR METHOD, BATCH SCAN) ===")
print(f"Catalogue margin — 25th pct: {round(q1, 1)}%, 75th pct: {round(q3, 1)}%, IQR: {round(iqr, 1)}")
print(f"Anomaly threshold (Q1 - 1.5xIQR): margin below {round(lower_fence, 1)}%")
print(f"Products flagged as margin anomalies: {anomaly_count} of {len(margin_data)} ({anomaly_pct}%)")

if anomaly_count:
    flagged = margin_data[margin_data['Margin Anomaly']][['Handle', 'Title', 'Variant Price', 'Cost per item', 'Margin %']]
    flagged = flagged.sort_values('Margin %')
    print("\nFlagged products (lowest margin first):")
    print(flagged.to_string(index=False))
    flagged.to_csv('../outputs/margin_anomaly_check.csv', index=False)
    print("\nSaved to outputs/margin_anomaly_check.csv")
else:
    print("\nNo margin anomalies found against this catalogue's own distribution.")
    pd.DataFrame(columns=['Handle', 'Title', 'Variant Price', 'Cost per item', 'Margin %']).to_csv(
        '../outputs/margin_anomaly_check.csv', index=False
    )

# Fold the anomaly count into the same summary file the Trust Score
# engine and dashboard already read, rather than creating a second,
# easy-to-miss source of truth for pricing health.
summary['margin_anomaly_count'] = anomaly_count
summary['margin_anomaly_pct'] = anomaly_pct
summary['margin_anomaly_threshold_pct'] = round(lower_fence, 1)
summary.to_csv('../outputs/pricing_integrity_summary.csv', index=False)
print("Margin anomaly stats added to outputs/pricing_integrity_summary.csv")
