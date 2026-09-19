# ===
# 01_data_cleaning.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ===
#
# WHY I BUILT THIS:
# Project 1 was written before the store had a single sale — every
# number in it was either synthetic or an honest zero. The catalogue
# behind that project has since been deleted (the pricing-integrity
# finding from Project 1 was one of the reasons) and replaced with a
# new one: 275 products, organised by category and by which country
# they actually ship to, with 7 real paid orders behind them now.
# This script is the same first step as Project 1's — turn the raw
# Shopify exports into something the rest of the pipeline can trust —
# but built for this new catalogue and, for the first time, real
# order data instead of a forecast.
#
# WHAT THE RAW DATA LOOKS LIKE:
# - products_export.csv: one row per variant/image again, same as
#   before, but this time the Type column is actually filled in for
#   most rows (only ~16% are blank, versus ~70% in the old catalogue)
#   and there's a "Shipping Destinations" field (UK / Nigeria / USA /
#   Worldwide) that didn't exist in Project 1's data at all.
# - orders_export.csv: Shopify repeats a whole order's columns once
#   per line item, so a 5-item order shows up as 5 rows with the same
#   order Total, Billing Country, Risk Level etc. copied down. Left
#   as-is, this would silently multiply revenue and order counts.
# - customers_export.csv: one row per customer, includes Total Spent
#   and Total Orders per customer as Shopify computed them — useful
#   as an independent cross-check on the orders file.
#
# DECISIONS I MADE:
# - Products: same "drop rows with no Title" rule as Project 1, then
#   keep the new Shipping Destinations field since it's the country
#   dimension this catalogue has that the old one didn't.
# - Orders: split into two tables — one row per ORDER (order_clean),
#   and one row per LINE ITEM (order_line_items_clean) — instead of
#   forcing everything into a single shape. Order-level questions
#   ("how much did we make", "which country") and line-item-level
#   questions ("which product sold") need different granularity, and
#   collapsing them into one table always meant getting one of the
#   two wrong.
# - Customers: kept as its own cleaned table so it can be used later
#   as an independent check against the orders total, the same way
#   this project checked Shopify's own Risk Level rather than
#   inventing a fraud score from scratch.
# ===

import pandas as pd

# Load raw exports from Shopify admin
raw_products = pd.read_csv('../raw_data/products_export.csv', low_memory=False)
raw_orders = pd.read_csv('../raw_data/orders_export.csv', low_memory=False)
raw_customers = pd.read_csv('../raw_data/customers_export.csv', low_memory=False)

print(f"Raw product rows loaded (variant/image rows): {len(raw_products)}")
print(f"Raw order rows loaded (line-item rows): {len(raw_orders)}")
print(f"Raw customer rows loaded: {len(raw_customers)}")


# ==========================================================
# PART 1 — PRODUCTS
# ==========================================================

# --
# STEP 1 — REMOVE INCOMPLETE ROWS
# --
# Same reasoning as Project 1: rows without a Title are variant-only
# or blank rows Shopify includes in the export, not real products.
# --

products_clean = raw_products.dropna(subset=['Title'])
products_clean = products_clean[products_clean['Title'].str.strip() != '']

rows_removed = len(raw_products) - len(products_clean)
print(f"\n[Products] Rows removed (no title): {rows_removed}")
print(f"[Products] Products remaining: {len(products_clean)}")

# --
# STEP 2 — KEEP ONLY RELEVANT COLUMNS
# --
# Added 'Shipping Destinations (...)' this time — it's the country
# dimension the new catalogue has. Renamed it to something readable
# since the raw column name carries the full Shopify metafield path.
# --

shipping_dest_col = 'Shipping Destinations (product.metafields.custom.shipping_destinations)'

useful_columns = [
    'Handle',
    'Title',
    'Vendor',
    'Type',
    'Tags',
    'Variant Price',
    'Variant Compare At Price',
    'Cost per item',
    shipping_dest_col,
    'Status',
]

products_clean = products_clean[useful_columns].rename(
    columns={shipping_dest_col: 'Shipping Destination'}
)

# --
# STEP 3 — FIX DATA TYPES AND FILL GAPS
# --
# Type is much better populated than Project 1's catalogue but still
# has gaps (~16%) — filled with 'Unknown' rather than dropped, same
# as before, since 02_product_classification.py will backfill these
# with keyword matching anyway.
#
# Shipping Destination has some blanks too (no destination metafield
# set) — filling those with 'Unspecified' rather than guessing.
# --

products_clean['Type'] = products_clean['Type'].fillna('Unknown')
products_clean['Shipping Destination'] = products_clean['Shipping Destination'].fillna('Unspecified')

products_clean['Variant Price'] = pd.to_numeric(products_clean['Variant Price'], errors='coerce')
products_clean['Variant Compare At Price'] = pd.to_numeric(products_clean['Variant Compare At Price'], errors='coerce')
products_clean['Cost per item'] = pd.to_numeric(products_clean['Cost per item'], errors='coerce')

# --
# STEP 4 — CALCULATE DISCOUNT % AND MARGIN
# --
# Discount % the same way Project 1 did it. Margin is new here —
# Project 1's catalogue didn't have Cost per item filled in reliably
# enough to trust a margin figure, but this export has it for 271 of
# 275 products, so it's worth calculating now that there are real
# orders to eventually check it against.
# --

products_clean['Discount %'] = (
    (products_clean['Variant Compare At Price'] - products_clean['Variant Price']) /
    products_clean['Variant Compare At Price'] * 100
).round(1)

products_clean['Margin %'] = (
    (products_clean['Variant Price'] - products_clean['Cost per item']) /
    products_clean['Variant Price'] * 100
).round(1)

discounted_count = products_clean['Discount %'].notna().sum()
margin_count = products_clean['Margin %'].notna().sum()
print(f"[Products] Products with a discount applied: {discounted_count}")
print(f"[Products] Products with a calculable margin: {margin_count}")

products_clean.to_csv('../cleaned_data/products_clean.csv', index=False)
print("[Products] Saved to cleaned_data/products_clean.csv")


# ==========================================================
# PART 2 — ORDERS
# ==========================================================
#
# Shopify's order export repeats the whole order on every line-item
# row. Grouping by order Name and taking the first value of each
# order-level column collapses that back down to one row per order —
# taking .sum() here instead would have silently multiplied Total by
# however many line items an order had, which is exactly the kind of
# quiet inflation this project has been built to catch, not repeat.
# --

order_level_columns = [
    'Name', 'Email', 'Financial Status', 'Created at', 'Currency',
    'Subtotal', 'Shipping', 'Taxes', 'Total',
    'Discount Code', 'Discount Amount',
    'Billing Country', 'Shipping Country', 'Risk Level',
]

orders_clean = raw_orders[order_level_columns].groupby('Name', as_index=False).first()
orders_clean['Created at'] = pd.to_datetime(orders_clean['Created at'], utc=True, errors='coerce')
orders_clean = orders_clean.sort_values('Created at').reset_index(drop=True)

print(f"\n[Orders] Line-item rows in raw export: {len(raw_orders)}")
print(f"[Orders] Real orders after collapsing to one row each: {len(orders_clean)}")
print(f"[Orders] Total revenue across real orders: £{orders_clean['Total'].sum():.2f}")

orders_clean.to_csv('../cleaned_data/orders_clean.csv', index=False)
print("[Orders] Saved to cleaned_data/orders_clean.csv")

# Line-item detail kept separately for anything that needs to know
# WHICH products sold, not just how many orders there were.
line_item_columns = [
    'Name', 'Lineitem name', 'Lineitem quantity', 'Lineitem price', 'Lineitem sku',
]
order_line_items_clean = raw_orders[line_item_columns].dropna(subset=['Lineitem name'])
order_line_items_clean.to_csv('../cleaned_data/order_line_items_clean.csv', index=False)
print(f"[Orders] Saved {len(order_line_items_clean)} line items to cleaned_data/order_line_items_clean.csv")


# ==========================================================
# PART 3 — CUSTOMERS
# ==========================================================
#
# Kept mostly as-is — this file is already one row per customer.
# Total Spent / Total Orders are Shopify's own running totals, kept
# here so a later script can check them against orders_clean.csv
# independently, the same way this project checks its own numbers
# rather than trusting a single source.
# --

customer_columns = [
    'Customer ID', 'First Name', 'Last Name', 'Email',
    'Default Address Country Code', 'Total Spent', 'Total Orders',
]
customers_clean = raw_customers[customer_columns].copy()
customers_clean.to_csv('../cleaned_data/customers_clean.csv', index=False)

print(f"\n[Customers] {len(customers_clean)} customer records saved to cleaned_data/customers_clean.csv")
print(f"[Customers] Sum of Total Spent across all customers: £{customers_clean['Total Spent'].sum():.2f}")
print(f"[Customers] Sum of Total Orders across all customers: {int(customers_clean['Total Orders'].sum())}")

# Quick cross-check right here rather than waiting for a test to
# catch it — if these two don't match, something is wrong before
# any other script even runs.
orders_total = round(orders_clean['Total'].sum(), 2)
customers_total = round(customers_clean['Total Spent'].sum(), 2)
if orders_total != customers_total:
    print(f"\n*** MISMATCH: orders_clean total £{orders_total} != customers_clean total £{customers_total} ***")
else:
    print(f"\nCross-check passed: orders_clean and customers_clean both total £{orders_total}")

print("\n=== CLEANING COMPLETE ===")
print("Ready for 02_product_classification.py")
