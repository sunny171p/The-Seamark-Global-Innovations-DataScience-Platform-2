# ==
# 10_external_category_benchmark.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ==
#
# WHY THIS EXISTS:
# 09_catalog_vs_sales_mix.py compares Seamark's own real catalogue mix
# against Seamark's own real sales — both sides are this store's data.
# This script adds a second, separate comparison: Seamark's real sales
# mix against a real EXTERNAL e-commerce dataset's real order mix, so
# there's an outside reference point for "is what we're selling in line
# with a comparable real business", not just an internal one.
#
# WHERE THE EXTERNAL DATA CAME FROM:
# The Olist Brazilian E-Commerce Public Dataset — a real, publicly
# documented dataset of 99,441 real orders (96,478 delivered) placed
# through the Olist marketplace, September 2016 to October 2018.
# Sunday downloaded it directly (Kaggle: olistbr/brazilian-ecommerce)
# and provided the four files this script actually uses:
#   raw_data/external_olist/olist_orders_dataset.csv
#   raw_data/external_olist/olist_order_items_dataset.csv
#   raw_data/external_olist/olist_products_dataset.csv
#   raw_data/external_olist/product_category_name_translation.csv
# Every number this script reports from that dataset is real — nothing
# here is simulated, sampled, or invented on either side of the
# comparison.
#
# WHAT THIS DELIBERATELY DOES NOT CLAIM:
# This is NOT "what Seamark should expect to sell" and it is NOT used
# to adjust, scale, or recalibrate any of Seamark's own real numbers
# anywhere else in this project (the AI Forecast stays untouched by
# this script). Olist is a different business — a general marketplace
# across ~70 categories, in Brazil, in 2016-2018 — not a direct
# competitor or an equivalent store. It's an external reference point
# for "does a large, real e-commerce dataset's category mix look
# roughly like ours", not a prediction. Because this is a % share of
# total comparison on each side, no currency conversion (BRL vs GBP)
# is needed or attempted — converting would add an assumption this
# script doesn't need to make.
#
# THE CATEGORY MAPPING, AND WHY IT'S CONSERVATIVE ON PURPOSE:
# Olist has ~70 category names; Seamark's rule-based classifier
# (02_product_classification.py) only has 14. Mapping every Olist
# category into one of Seamark's 14 would mean guessing at categories
# Seamark doesn't carry (e.g. 'furniture_living_room', 'agro_industry')
# — instead, only Olist categories with a clear, defensible match to
# how 02_product_classification.py actually defines each Seamark
# category (its TYPE_GROUPS dict and keyword rules) are mapped in;
# everything else — including Olist categories that are plausibly
# related but not a clean match (e.g. 'baby', 'cool_stuff',
# 'computers_accessories') — falls into 'Other' rather than being
# force-fit. This underestimates a few of Seamark's categories rather
# than overstating the match, which is the safer direction to be wrong
# in for a comparison like this.
# ==

import pandas as pd

orders = pd.read_csv('../raw_data/external_olist/olist_orders_dataset.csv')
items = pd.read_csv('../raw_data/external_olist/olist_order_items_dataset.csv')
products = pd.read_csv('../raw_data/external_olist/olist_products_dataset.csv')
category_translation = pd.read_csv('../raw_data/external_olist/product_category_name_translation.csv')

seamark_mix = pd.read_csv('../outputs/catalog_vs_sales_mix.csv')

print(f"Olist real orders loaded    : {len(orders)}")
print(f"Olist real order items loaded : {len(items)}")


# --
# STEP 1 — KEEP ONLY DELIVERED ORDERS (a completed real transaction,
# same standard a 'real order' means elsewhere in this project)
# --

delivered_order_ids = set(orders.loc[orders['order_status'] == 'delivered', 'order_id'])
delivered_items = items[items['order_id'].isin(delivered_order_ids)].copy()
print(f"Olist order items on delivered orders : {len(delivered_items)} of {len(items)}")


# --
# STEP 2 — MATCH EACH ITEM TO ITS REAL ENGLISH CATEGORY NAME
# --

products_with_category = products.merge(category_translation, on='product_category_name', how='left')
delivered_items = delivered_items.merge(
    products_with_category[['product_id', 'product_category_name_english']],
    on='product_id', how='left',
)
matched = delivered_items['product_category_name_english'].notna().sum()
print(f"Delivered items matched to an English category name : {matched} of {len(delivered_items)}")


# --
# STEP 3 — MAP OLIST'S REAL CATEGORIES ONTO SEAMARK'S 14, CONSERVATIVELY
# (see header comment for why unmatched Olist categories become 'Other'
# instead of being guessed into one of Seamark's buckets)
# --

OLIST_TO_SEAMARK_CATEGORY = {
    # Footwear — Seamark's Footwear = Shopify Type 'Footwear' / keyword 'shoe'
    'fashion_shoes': 'Footwear',
    # Watches — Seamark's Watches = Shopify Type 'Watches'
    'watches_gifts': 'Watches',
    # Apparel — Seamark's Apparel = Shopify Type 'Tops'/'Bottoms'
    'fashion_male_clothing': 'Apparel',
    'fashio_female_clothing': 'Apparel',
    'fashion_underwear_beach': 'Apparel',
    'fashion_sport': 'Apparel',
    # Toys — Seamark's Toys = Shopify Type 'Toys'
    'toys': 'Toys',
    # Fitness Equipment — Seamark's Fitness Equipment = Shopify Type 'Fitness Equipment'
    'sports_leisure': 'Fitness Equipment',
    # Children's Clothing — Seamark's = Shopify Type "Children's Clothing"
    'fashion_childrens_clothes': "Children's Clothing",
    # Audio — Seamark's Audio = Shopify Type 'Headphones'/'Speakers'
    'audio': 'Audio',
    # Home & Lighting — Seamark's = Shopify Type 'Lighting'/'Home Appliances'
    # or keyword 'light'/'lamp'/'led'
    'housewares': 'Home & Lighting',
    'home_confort': 'Home & Lighting',
    'home_comfort_2': 'Home & Lighting',
    'construction_tools_lights': 'Home & Lighting',
    'home_appliances': 'Home & Lighting',
    'home_appliances_2': 'Home & Lighting',
    # Pet Supplies — Seamark's = Shopify Type 'Pet Supplies' or keyword 'pet'/'cat'/'dog'
    'pet_shop': 'Pet Supplies',
    # Smartphones — Seamark's Smartphones = Shopify Type 'Smartphones'/'Mobile Phones'
    # (Olist's 'fixed_telephony' is landlines, not smartphones — excluded on purpose)
    'telephony': 'Smartphones',
    # Bags & Accessories — Seamark's = Shopify Type 'Bags & Wallets'/'Jewelry'/'Hats'
    # or keyword 'bag'/'wallet'/'necklace'/'bracelet'/'ring'/'jewel'
    'fashion_bags_accessories': 'Bags & Accessories',
    'luggage_accessories': 'Bags & Accessories',
    # Office Supplies — Seamark's = Shopify Type 'Office Supplies'
    'stationery': 'Office Supplies',
    # Beauty & Personal Care — Seamark's = Shopify Type 'Beauty & Personal Care'
    'health_beauty': 'Beauty & Personal Care',
    'perfumery': 'Beauty & Personal Care',
}

delivered_items['seamark_category'] = (
    delivered_items['product_category_name_english'].map(OLIST_TO_SEAMARK_CATEGORY).fillna('Other')
)

mapped_count = (delivered_items['seamark_category'] != 'Other').sum()
print(
    f"Delivered items mapped to a Seamark category (not 'Other') : "
    f"{mapped_count} of {len(delivered_items)} ({mapped_count / len(delivered_items) * 100:.1f}%)"
)


# --
# STEP 4 — REAL REVENUE MIX ON EACH SIDE (% of total, so no currency
# conversion is needed to compare them)
# --

olist_revenue_by_category = delivered_items.groupby('seamark_category')['price'].sum()
olist_pct = (olist_revenue_by_category / olist_revenue_by_category.sum() * 100).round(1)

comparison = pd.DataFrame({
    'seamark_real_sales_pct': seamark_mix.set_index('auto_category')['real_sales_pct'],
    'external_olist_revenue_pct': olist_pct,
}).fillna(0.0).reset_index().rename(columns={'index': 'auto_category'})

comparison = comparison.sort_values('external_olist_revenue_pct', ascending=False).reset_index(drop=True)

print("\n=== SEAMARK REAL SALES MIX vs EXTERNAL (OLIST) REAL ORDER MIX, BY CATEGORY ===")
print(comparison.to_string(index=False))

biggest_gap_row = (comparison['seamark_real_sales_pct'] - comparison['external_olist_revenue_pct']).abs().idxmax()
biggest_gap = comparison.loc[biggest_gap_row]
print(
    f"\nBiggest gap: {biggest_gap['auto_category']} is {biggest_gap['seamark_real_sales_pct']}% of Seamark's "
    f"real sales vs {biggest_gap['external_olist_revenue_pct']}% of the external Olist dataset's real orders."
)
print(
    "This is a comparison against one large, real, but unrelated business — not a target or a prediction. "
    "Seamark's own real sales mix is built from only 11 real line items, so treat this as directional, "
    "not conclusive, on both sides of a small-sample-vs-large-external-sample comparison."
)

comparison.to_csv('../outputs/external_category_benchmark.csv', index=False)
print("\nSummary saved to outputs/external_category_benchmark.csv")
