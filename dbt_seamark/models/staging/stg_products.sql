-- ==
-- stg_products.sql
-- Author: Sunday Emmanuel Azeez
-- ==
-- Renames products_clean's Shopify-export column names to plain
-- snake_case, and keeps only the columns the marts actually use.
-- No real customer data touches this model, products are catalog
-- data, not personal data.

select
    "Handle"                    as product_handle,
    "Title"                     as product_title,
    "Vendor"                    as vendor,
    "Type"                      as product_type,
    "Variant Price"             as price,
    "Variant Compare At Price"  as compare_at_price,
    "Cost per item"             as cost_per_item,
    "Status"                    as status,
    "Discount %"                as discount_pct,
    "Margin %"                  as margin_pct,
    "Auto_Category"             as category
from {{ source('seamark', 'products_clean') }}
