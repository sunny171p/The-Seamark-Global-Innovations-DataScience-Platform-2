# ==
# 09_catalog_vs_sales_mix.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY THIS EXISTS:
# "Is what's actually selling the same as what we stocked?" is a real
# question, and this store has real data on both sides of it — the 275
# products in the catalogue, and the real line items inside the 7 real
# orders. No simulated or invented data was needed to answer it.
#
# WHAT THIS DELIBERATELY DID NOT DO:
# An earlier idea for this check was to generate a "1,000 simulated
# order" dataset and treat its category breakdown as the "expected"
# side of the comparison. That would have meant putting fabricated
# numbers on the dashboard labelled as if they were a real prediction.
# This script uses the store's own real catalogue mix as the "expected"
# side instead — what share of the 275 products sit in each category
# is a real, true fact about this store, and a reasonable proxy for
# "what we expected to sell", since it's literally what the business
# chose to stock.
#
# HOW A REAL LINE ITEM GETS MATCHED TO A CATEGORY:
# order_line_items_clean.csv has no category column of its own — it
# only has a product name and (usually) a variant SKU. This matches
# each line item to a real product two ways, in order:
#   1. By 'Lineitem sku' against products_export.csv's 'Variant SKU'
#      (exact match) — covers 9 of this store's 11 real line items.
#   2. Where no SKU is present, by exact 'Lineitem name' against the
#      product's 'Title' — covers the remaining 2 (two Xiaomi phones
#      whose order rows have a blank SKU, but whose full title matches
#      a real product exactly).
# All 11 of this store's real line items matched a real product this
# way — nothing here is estimated or guessed.
#
# THE SAMPLE SIZE CAVEAT, STATED PLAINLY:
# 11 real line items across 7 real orders is a very small sample. A
# category mix built from that many rows can shift a lot with the next
# few orders. This script reports the real numbers as they are today,
# not as a stable long-run trend — the dashboard says so too.
# ==

import pandas as pd

products = pd.read_csv('../cleaned_data/products_clean.csv')
raw_products = pd.read_csv('../raw_data/products_export.csv', low_memory=False)
line_items = pd.read_csv('../cleaned_data/order_line_items_clean.csv')

print(f"Real line items to match : {len(line_items)}")
print(f"Products in catalogue     : {len(products)}")


# --
# STEP 1 — MATCH EACH REAL LINE ITEM TO A REAL PRODUCT'S CATEGORY
# --

sku_to_handle = (
    raw_products.dropna(subset=['Variant SKU'])
    .drop_duplicates('Variant SKU')
    .set_index('Variant SKU')['Handle']
)
title_to_handle = (
    raw_products.dropna(subset=['Title'])
    .drop_duplicates('Title')
    .set_index('Title')['Handle']
)

line_items['matched_handle'] = line_items['Lineitem sku'].map(sku_to_handle)
still_missing = line_items['matched_handle'].isna()
line_items.loc[still_missing, 'matched_handle'] = (
    line_items.loc[still_missing, 'Lineitem name'].map(title_to_handle)
)

matched_count = line_items['matched_handle'].notna().sum()
print(f"Line items matched to a real product : {matched_count} of {len(line_items)}")
if matched_count < len(line_items):
    print("(Unmatched rows are excluded from the sales-mix side below, not guessed at.)")

line_items = line_items.merge(
    products[['Handle', 'Auto_Category']],
    left_on='matched_handle', right_on='Handle', how='left',
)
line_items['line_revenue_gbp'] = line_items['Lineitem quantity'] * line_items['Lineitem price']


# --
# STEP 2 — CATALOGUE MIX (real, what the store actually stocks)
# --

catalog_counts = products['Auto_Category'].value_counts()
catalog_pct = (catalog_counts / catalog_counts.sum() * 100).round(1)


# --
# STEP 3 — REAL SALES MIX (real, what real orders actually bought)
# --

matched_items = line_items.dropna(subset=['Auto_Category'])
sales_revenue = matched_items.groupby('Auto_Category')['line_revenue_gbp'].sum().sort_values(ascending=False)
sales_pct = (sales_revenue / sales_revenue.sum() * 100).round(1) if sales_revenue.sum() else sales_revenue


# --
# STEP 4 — COMBINE AND SAVE
# --

comparison = pd.DataFrame({
    'catalog_product_count': catalog_counts,
    'catalog_pct': catalog_pct,
    'real_sales_revenue_gbp': sales_revenue,
    'real_sales_pct': sales_pct,
}).fillna(0.0)
comparison['real_sales_revenue_gbp'] = comparison['real_sales_revenue_gbp'].round(2)
comparison = comparison.sort_values('catalog_pct', ascending=False).reset_index()
comparison = comparison.rename(columns={comparison.columns[0]: 'auto_category'})

print("\n=== CATALOGUE MIX vs REAL SALES MIX (by category) ===")
print(comparison.to_string(index=False))

biggest_gap_row = (comparison['real_sales_pct'] - comparison['catalog_pct']).abs().idxmax()
biggest_gap = comparison.loc[biggest_gap_row]
print(
    f"\nBiggest gap: {biggest_gap['auto_category']} is {biggest_gap['catalog_pct']}% of the catalogue "
    f"but {biggest_gap['real_sales_pct']}% of real sales revenue so far."
)
print(
    "This is a real pattern in a very small dataset (11 line items) — worth watching as more "
    "real orders come in, not yet a stable conclusion."
)

comparison.to_csv('../outputs/catalog_vs_sales_mix.csv', index=False)
print("\nSummary saved to outputs/catalog_vs_sales_mix.csv")
