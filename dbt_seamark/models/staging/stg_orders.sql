-- ==
-- stg_orders.sql
-- Author: Sunday Emmanuel Azeez
-- ==
-- Email is deliberately left out of this select. Nothing downstream
-- of this staging layer needs a customer's email address to compute
-- financial or logistics numbers, and the fewer models that touch a
-- real customer's personal data, the fewer places a future mistake
-- could expose it. This is the same reasoning DATA_PROVENANCE.md and
-- CASE_STUDY.md already document for the rest of the project, applied
-- here too.

select
    "Name"             as order_name,
    "Financial Status" as financial_status,
    "Created at"        as created_at,
    "Currency"          as currency,
    "Subtotal"          as subtotal,
    "Shipping"          as shipping,
    "Taxes"             as taxes,
    "Total"             as total,
    "Discount Code"     as discount_code,
    "Discount Amount"   as discount_amount,
    "Billing Country"   as billing_country,
    "Shipping Country"  as shipping_country,
    "Risk Level"        as risk_level
from {{ source('seamark', 'orders_clean') }}
