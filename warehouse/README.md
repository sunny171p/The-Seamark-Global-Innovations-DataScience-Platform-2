# The DuckDB warehouse — idempotent by design, not "incremental," and here's why

`build_duckdb.py` loads every CSV in `cleaned_data/` and `outputs/` into
`warehouse/seamark.duckdb`, one table per CSV, so a question that would
otherwise mean opening two files and joining them by hand in pandas
becomes one SQL query instead. Nothing else about the pipeline changes:
the CSVs are still the real source of truth, and `tests/` still checks
its numbers against them directly, not against this file.

## What "idempotent" actually means here, and how it's checked

Running `python warehouse/build_duckdb.py` any number of times in a row
against the same `cleaned_data/`/`outputs/` produces the exact same
warehouse every time — not just tables that look right, the literal
same table list and the literal same rows. Two things make that true:

- Every table is loaded with `CREATE OR REPLACE TABLE`, so a table for
  a CSV that already existed is fully replaced, never appended to or
  duplicated, no matter how many times this runs.
- Every run also drops any table that no longer has a matching CSV.
  Without this, a CSV that got renamed or stopped being produced would
  leave its old table sitting in `seamark.duckdb` forever — the
  warehouse would depend on this script's own run history instead of
  only on what's actually on disk right now. That's the part that
  wasn't true before, and now is.

`tests/test_warehouse.py` proves both of these automatically: it builds
the warehouse twice in a row and asserts the table list and every
table's row count come out identical, and separately proves a stale
table left over from an old CSV actually gets dropped on the next run.
Worth running yourself rather than trusting this file:

```
pip install -r requirements.txt
python -m pytest tests/test_warehouse.py -v
```

## Why this isn't "incremental" loading, on purpose

Every CSV this script reads is already a **full recomputation** from
`raw_data/`, produced fresh by `pipeline.py` on every run — not an
append-only log with new rows showing up at the end. Loading it
"incrementally" would mean diffing each new CSV against the version
loaded last time to work out which rows actually changed, real
complexity, for a source that's already telling you the whole current
answer every time it's written. At this project's real size (275
products, a handful of real orders) that complexity would buy nothing:
a full `CREATE OR REPLACE TABLE` reload takes a fraction of a second.

The part of this project that genuinely **is** incremental and
append-only is `shopify_sync/fold_webhook_events.py` — each real order
event lands as its own file the moment it happens, gets folded into
`raw_data/orders_export.csv` as new rows, and its source file is moved
into `processed/` so it's never folded in twice. That script already
handles this correctly on its own; nothing needed to change there for
this warehouse layer, and it's a genuinely different kind of problem
from "reload some CSVs into DuckDB."

## Using it

```
python pipeline.py                  # if you haven't already
python warehouse/build_duckdb.py
duckdb warehouse/seamark.duckdb -c "SELECT * FROM funnel_summary;"
```

`seamark.duckdb` is gitignored — it's a derived, rebuildable file, not
raw data, and it's also what `dbt_seamark/` reads from (see
`dbt_seamark/profiles.yml`), so the two additions share one source
instead of loading the same CSVs twice.
