# ==
# schemas.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The test suite already checks that specific numbers are correct, by
# recomputing them independently. What it doesn't check on its own is
# the *shape* of the data going in, whether a column is still named
# what a script expects, whether a price ever came back negative,
# whether a required field went missing. A silent schema change
# upstream (Shopify renaming an export column, say) could slip through
# and only show up as a confusing downstream error several stages
# later. These schemas catch that earlier, at the door, with a clear
# message about exactly what changed.
#
# This uses Pandera because it's lightweight, pure Python, and reads
# like a plain description of what a column should look like, no
# separate server or project setup needed, which matches the scale of
# this project honestly.

import pandera.pandas as pa
from pandera.pandas import Column, Check, DataFrameSchema

# --
# products_clean.csv (Stage 1 output)
# --
products_schema = DataFrameSchema(
    {
        "Handle": Column(str, Check.str_length(min_value=1), unique=True, nullable=False),
        "Title": Column(str, nullable=False),
        "Variant Price": Column(float, Check.ge(0), nullable=False),
        "Variant Compare At Price": Column(float, Check.ge(0), nullable=True),
        "Cost per item": Column(float, Check.ge(0), nullable=True),
        "Status": Column(str, nullable=False),
        "Discount %": Column(float, nullable=True),
        "Margin %": Column(float, nullable=True),
        "Auto_Category": Column(str, nullable=False),
    },
    strict=False,  # extra columns (Vendor, Type, Tags, ...) are fine, not every column needs a rule
    coerce=True,
)

# --
# orders_clean.csv (Stage 1 output)
# --
# Deliberately no check touches the Email column's actual value here.
# A validation failure on Email would risk printing a real customer's
# address into a terminal or a log file, exactly the kind of exposure
# this project already had one real incident with (see CASE_STUDY.md).
# Checking that the column exists is enough for a schema check to be
# useful without ever inspecting the value.
#
# Email is marked nullable on purpose, not an oversight: checked
# against this store's real data, one order out of the current seven
# has no email at all, and that's already true in the raw Shopify
# export this pipeline reads from, not something the cleaning step
# introduced. A real order placed without an email (a phone order, an
# in-person sale entered manually) is a normal thing for a small store
# to have, so a schema rule that treated it as a failure would be
# flagging correct data as broken.
orders_schema = DataFrameSchema(
    {
        "Name": Column(str, unique=True, nullable=False),
        "Email": Column(str, nullable=True),
        "Financial Status": Column(
            str,
            Check.isin(["paid", "pending", "refunded", "partially_refunded", "voided", "authorized"]),
            nullable=False,
        ),
        "Currency": Column(str, nullable=False),
        "Subtotal": Column(float, Check.ge(0), nullable=False),
        "Total": Column(float, Check.ge(0), nullable=False),
    },
    strict=False,
    coerce=True,
)

# --
# order_line_items_clean.csv (Stage 1 output)
# --
order_line_items_schema = DataFrameSchema(
    {
        "Name": Column(str, nullable=False),
        "Lineitem name": Column(str, nullable=False),
        "Lineitem quantity": Column(int, Check.gt(0), nullable=False),
        "Lineitem price": Column(float, Check.ge(0), nullable=False),
    },
    strict=False,
    coerce=True,
)

SCHEMAS_BY_FILENAME = {
    "products_clean.csv": products_schema,
    "orders_clean.csv": orders_schema,
    "order_line_items_clean.csv": order_line_items_schema,
}
