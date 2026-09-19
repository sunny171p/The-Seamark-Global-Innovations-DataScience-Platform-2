-- ==
-- mart_category_sales_mix.sql
-- Author: Sunday Emmanuel Azeez
-- ==
-- The same question analytics/09_catalog_vs_sales_mix.py already
-- answers in pandas: for each category, how many products are in the
-- catalog versus how many units actually sold. Answered here a second
-- way, in SQL, against the DuckDB tables build_duckdb.py loads from
-- the same CSVs, so the two answers can be checked against each other.
--
-- One honest caveat: this join matches line items to products by
-- product title, since products_clean doesn't currently carry a SKU
-- column to join on directly. CASE_STUDY.md documents a real bug the
-- Python pipeline hit from exactly this kind of mismatch (matching by
-- title instead of a stable SKU, once a product had more than one
-- variant). For a small catalog with mostly one variant per product
-- this still lines up, but if products_clean ever gains a real SKU
-- column, this join should move to it instead of a title match.

with catalog as (
    select
        category,
        count(*) as catalog_product_count
    from {{ ref('stg_products') }}
    group by category
),

sales as (
    select
        p.category,
        sum(li.quantity)                as units_sold,
        sum(li.quantity * li.unit_price) as revenue
    from {{ ref('stg_order_line_items') }} li
    left join {{ ref('stg_products') }} p
        on li.product_title = p.product_title
    group by p.category
)

select
    catalog.category,
    catalog.catalog_product_count,
    coalesce(sales.units_sold, 0) as units_sold,
    coalesce(sales.revenue, 0)    as revenue
from catalog
left join sales on catalog.category = sales.category
order by revenue desc
