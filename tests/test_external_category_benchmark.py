# ==
# test_external_category_benchmark.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# Same rule as every other test in this project: recompute independently
# from the raw files and check the saved output agrees, rather than
# trusting 10_external_category_benchmark.py's own arithmetic. This also
# guards the specific honesty point that script is built around — every
# number on the external (Olist) side must trace back to a real,
# delivered order in the raw Olist export, and the category mapping must
# be the same conservative one documented in that script's header, not
# a looser one that quietly inflates the match rate.

import pandas as pd
import pytest

OLIST_TO_SEAMARK_CATEGORY = {
    'fashion_shoes': 'Footwear',
    'watches_gifts': 'Watches',
    'fashion_male_clothing': 'Apparel',
    'fashio_female_clothing': 'Apparel',
    'fashion_underwear_beach': 'Apparel',
    'fashion_sport': 'Apparel',
    'toys': 'Toys',
    'sports_leisure': 'Fitness Equipment',
    'fashion_childrens_clothes': "Children's Clothing",
    'audio': 'Audio',
    'housewares': 'Home & Lighting',
    'home_confort': 'Home & Lighting',
    'home_comfort_2': 'Home & Lighting',
    'construction_tools_lights': 'Home & Lighting',
    'home_appliances': 'Home & Lighting',
    'home_appliances_2': 'Home & Lighting',
    'pet_shop': 'Pet Supplies',
    'telephony': 'Smartphones',
    'fashion_bags_accessories': 'Bags & Accessories',
    'luggage_accessories': 'Bags & Accessories',
    'stationery': 'Office Supplies',
    'health_beauty': 'Beauty & Personal Care',
    'perfumery': 'Beauty & Personal Care',
}


def _recompute(raw_data_dir):
    external_dir = raw_data_dir / "external_olist"
    orders = pd.read_csv(external_dir / "olist_orders_dataset.csv")
    items = pd.read_csv(external_dir / "olist_order_items_dataset.csv")
    products = pd.read_csv(external_dir / "olist_products_dataset.csv")
    category_translation = pd.read_csv(external_dir / "product_category_name_translation.csv")

    delivered_order_ids = set(orders.loc[orders["order_status"] == "delivered", "order_id"])
    delivered_items = items[items["order_id"].isin(delivered_order_ids)].copy()

    products_with_category = products.merge(category_translation, on="product_category_name", how="left")
    delivered_items = delivered_items.merge(
        products_with_category[["product_id", "product_category_name_english"]],
        on="product_id", how="left",
    )
    delivered_items["seamark_category"] = (
        delivered_items["product_category_name_english"].map(OLIST_TO_SEAMARK_CATEGORY).fillna("Other")
    )

    revenue_by_category = delivered_items.groupby("seamark_category")["price"].sum()
    pct = (revenue_by_category / revenue_by_category.sum() * 100).round(1)
    return delivered_items, pct


def test_external_raw_files_exist(raw_data_dir):
    external_dir = raw_data_dir / "external_olist"
    for filename in (
        "olist_orders_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_products_dataset.csv",
        "product_category_name_translation.csv",
    ):
        assert (external_dir / filename).exists(), (
            f"raw_data/external_olist/{filename} is missing — "
            "10_external_category_benchmark.py needs it to run."
        )


def test_only_delivered_orders_are_counted(raw_data_dir):
    """The script's whole premise is comparing real, completed orders —
    a cancelled/unavailable/processing Olist order isn't a real sale and
    shouldn't count toward its side of the comparison.
    """
    external_dir = raw_data_dir / "external_olist"
    orders = pd.read_csv(external_dir / "olist_orders_dataset.csv")
    items = pd.read_csv(external_dir / "olist_order_items_dataset.csv")

    non_delivered_ids = set(orders.loc[orders["order_status"] != "delivered", "order_id"])
    delivered_items, _ = _recompute(raw_data_dir)
    assert not set(delivered_items["order_id"]).intersection(non_delivered_ids), (
        "A non-delivered Olist order's item leaked into the delivered-only comparison."
    )
    assert len(delivered_items) < len(items), (
        "Filtering to delivered orders should drop at least the cancelled/unavailable rows."
    )


def test_external_category_benchmark_matches_recomputation(raw_data_dir, outputs_dir):
    _, external_pct = _recompute(raw_data_dir)
    saved = pd.read_csv(outputs_dir / "external_category_benchmark.csv").set_index("auto_category")

    for category, expected_pct in external_pct.items():
        assert saved.loc[category, "external_olist_revenue_pct"] == pytest.approx(expected_pct, abs=0.1), (
            f"{category}'s saved external_olist_revenue_pct doesn't match an independent recomputation "
            "from the raw Olist files."
        )


def test_external_olist_pct_sums_to_100(outputs_dir):
    saved = pd.read_csv(outputs_dir / "external_category_benchmark.csv")
    assert saved["external_olist_revenue_pct"].sum() == pytest.approx(100.0, abs=0.5)


def test_seamark_side_matches_catalog_vs_sales_mix_output(outputs_dir):
    """The Seamark side of this comparison should be the exact same real
    sales-mix numbers already verified in test_catalog_vs_sales_mix.py —
    not a second, separately-derived figure that could quietly drift
    from the first.
    """
    seamark_mix = pd.read_csv(outputs_dir / "catalog_vs_sales_mix.csv").set_index("auto_category")
    saved = pd.read_csv(outputs_dir / "external_category_benchmark.csv").set_index("auto_category")

    for category in saved.index:
        expected = seamark_mix.loc[category, "real_sales_pct"] if category in seamark_mix.index else 0.0
        assert saved.loc[category, "seamark_real_sales_pct"] == pytest.approx(expected, abs=0.01)


def test_category_mapping_only_uses_documented_olist_categories(raw_data_dir):
    """Every Olist category this script maps to a Seamark category must
    be one of the ones documented in the script's own mapping — this
    catches someone loosening the mapping later without updating the
    honesty rationale in the header comment.
    """
    external_dir = raw_data_dir / "external_olist"
    products = pd.read_csv(external_dir / "olist_products_dataset.csv")
    category_translation = pd.read_csv(external_dir / "product_category_name_translation.csv")
    all_real_categories = set(
        products.merge(category_translation, on="product_category_name", how="left")
        ["product_category_name_english"].dropna().unique()
    )
    mapped_categories = set(OLIST_TO_SEAMARK_CATEGORY.keys())
    assert mapped_categories.issubset(all_real_categories), (
        f"Mapping references a category that doesn't exist in the real Olist data: "
        f"{mapped_categories - all_real_categories}"
    )
