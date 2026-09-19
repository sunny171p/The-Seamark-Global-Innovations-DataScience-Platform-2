-- ==
-- stg_order_line_items.sql
-- Author: Sunday Emmanuel Azeez
-- ==
-- One row per line item. No customer name or email lives on this
-- table in the source data, so nothing needs to be filtered out here.

select
    "Name"              as order_name,
    "Lineitem name"     as product_title,
    "Lineitem quantity" as quantity,
    "Lineitem price"    as unit_price,
    "Lineitem sku"      as sku
from {{ source('seamark', 'order_line_items_clean') }}
