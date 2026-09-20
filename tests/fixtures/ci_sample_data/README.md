# CI sample data

These two files exist only so GitHub Actions can run the *real*
`pipeline.py` end to end on every push, to prove the code itself still
works, not just that previously-saved output files look right.

`raw_data/orders_export.csv` and `raw_data/customers_export.csv` are
gitignored on purpose (see the root `.gitignore` and
`DATA_PROVENANCE.md`) because the real ones hold real customer names
and emails. A fresh clone, including CI, never has them. The CI
workflow copies the two files in this folder into `raw_data/` for one
throwaway run inside the GitHub Actions runner, then discards the
whole checkout afterwards -- nothing here ever touches your real
`raw_data/`, `cleaned_data/`, or `outputs/` on your own machine or in
the actual committed repo.

Every name, email, and order in these two files is made up, written to
be obviously fake at a glance (`Sample Buyer One`,
`sample.buyer1@example.test`), and exists purely to give the pipeline
something with the right shape to run against. The Lineitem SKUs
below are real SKUs from the real, already-public `products_export.csv`
catalogue (no PII in that file), used here only so
`09_catalog_vs_sales_mix.py` has something real to match against
instead of coming back empty. Nothing computed from these two files is
ever presented anywhere in this project as a real business finding --
their only job is to make sure the pipeline still runs clean.
