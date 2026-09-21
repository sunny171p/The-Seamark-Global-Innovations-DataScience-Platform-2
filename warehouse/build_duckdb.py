# ==
# build_duckdb.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# The pipeline's actual source of truth is still the CSVs in cleaned_data/
# and outputs/, and the test suite still checks its numbers against those
# files directly. Nothing about that changes here, and nothing about it
# should. What this script adds is a second, queryable copy of the same
# data: every one of those CSVs loaded into a single local DuckDB file,
# seamark.duckdb, as real tables you can run SQL against.
#
# The reason for that is simple. Right now, answering a question like
# "which category had the best margin-to-price ratio across the last two
# stages" means opening two CSVs and joining them by hand in pandas.
# With this file built, it's one SQL query, and it's the same file dbt
# reads from in dbt_seamark/, so the two additions share one source
# instead of duplicating the loading logic twice.
#
# DuckDB was picked over a real server-based warehouse on purpose. It
# needs no server, no credentials, and no network call, it is just a
# file on disk, which matches the size of this project honestly: eleven
# real orders do not need a hosted data warehouse, but the project is
# still built the way a bigger one would need to work.
#
# IDEMPOTENT, ON PURPOSE, AND NOW ACTUALLY GUARANTEED:
# Running this script twice in a row against the same CSVs produces the
# exact same warehouse, not just the same-looking one. Every table is
# loaded with CREATE OR REPLACE, so re-running never duplicates a single
# row -- that part was already true before this note was added. What
# was missing: if a CSV that used to exist got renamed or removed (an
# old outputs/ file from a stage that no longer runs, say), its table
# stayed behind in seamark.duckdb forever, because nothing ever told the
# warehouse to forget it. Two consecutive runs of the OLD version of
# this script could therefore leave two DIFFERENT sets of tables behind,
# depending on what used to exist -- not actually idempotent, just
# usually close enough not to notice on a project this small. This
# version fixes that directly: every run now drops any table that
# doesn't correspond to a CSV file that exists right now, so the
# warehouse always exactly mirrors the current cleaned_data/ and
# outputs/ folders, however many times you run it, and however the
# source files have changed since the last run. tests/test_warehouse.py
# proves this automatically -- two consecutive builds compared table for
# table and row for row -- rather than asking anyone to trust this
# comment.
#
# WHY THIS ISN'T "INCREMENTAL" LOADING, ON PURPOSE:
# See warehouse/README.md for the full reasoning. Short version: every
# CSV in cleaned_data/ and outputs/ is already a full recomputation from
# raw_data/ on each pipeline.py run, not an append-only log -- so a
# row-level incremental load would mean tracking deltas against a
# source that doesn't have deltas, real complexity with no real payoff
# at this data's size. The one genuinely incremental, append-only part
# of this project is shopify_sync/fold_webhook_events.py, which already
# handles that correctly (each landed event file is moved to processed/
# the moment it's folded in, so nothing is ever double-counted) -- see
# that script's own header for how.
#
# USAGE:
#   pip install -r requirements.txt   (duckdb is in there)
#   python pipeline.py                (if you haven't already; this
#                                       script only reads what pipeline.py
#                                       already produced, it never
#                                       generates numbers of its own)
#   python warehouse/build_duckdb.py
#
# That leaves warehouse/seamark.duckdb sitting next to this script,
# gitignored, since it is a derived, rebuildable file, not raw data. Run
# it again any time -- including with a completely different set of
# cleaned_data/outputs files than last time -- and it converges to a
# warehouse that matches exactly what's on disk right now, nothing left
# over from before.

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = PROJECT_ROOT / "cleaned_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DB_PATH = Path(__file__).resolve().parent / "seamark.duckdb"

# Not a real CSV-derived table -- excluded from the stale-table cleanup
# below so the build's own record of itself never gets treated as an
# orphan and dropped.
METADATA_TABLE = "_build_metadata"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("build_duckdb")


def _table_name_for(csv_path: Path) -> str:
    """products_clean.csv -> products_clean, funnel_summary.csv -> funnel_summary."""
    return csv_path.stem


def load_csvs_from(con: duckdb.DuckDBPyConnection, folder: Path, source_label: str) -> tuple[int, int]:
    """Loads every CSV in folder as its own table. Returns (files loaded,
    total rows loaded) so the caller can record both in _build_metadata.
    """
    if not folder.exists():
        log.warning("%s does not exist yet, skipping (run pipeline.py first)", folder)
        return 0, 0

    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        log.warning("No CSV files found in %s", folder)
        return 0, 0

    loaded = 0
    rows_loaded = 0
    for csv_path in csv_files:
        table_name = _table_name_for(csv_path)
        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            log.error("Could not read %s: %s -- skipped", csv_path.name, exc)
            continue

        con.register("tmp_df", df)
        con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM tmp_df')
        con.unregister("tmp_df")
        log.info("Loaded %-40s -> table %-35s (%d rows, %d cols) [%s]",
                  csv_path.name, table_name, len(df), len(df.columns), source_label)
        loaded += 1
        rows_loaded += len(df)

    return loaded, rows_loaded


def _drop_stale_tables(con: duckdb.DuckDBPyConnection, expected_tables: set[str]) -> list[str]:
    """Drops any table in the database that doesn't correspond to a CSV
    file that exists right now. This is what makes re-running this
    script actually idempotent, not just non-duplicating: without it, a
    table from a CSV that was later renamed or removed would sit in
    seamark.duckdb forever, so the warehouse's table list would depend
    on this script's own run history instead of only on the current
    contents of cleaned_data/ and outputs/. Returns the names dropped,
    so the caller can log them.
    """
    existing = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    stale = sorted(existing - expected_tables - {METADATA_TABLE})
    for table_name in stale:
        con.execute(f'DROP TABLE "{table_name}"')
    return stale


def build(db_path: Path = DB_PATH) -> dict:
    """Does the actual build against db_path, and returns a small summary
    dict ({tables, rows, dropped}) so both main() and the test suite can
    use the same code path -- the test suite calls this directly against
    a throwaway path rather than reimplementing the load logic.
    """
    log.info("Building DuckDB warehouse at %s", db_path)
    con = duckdb.connect(str(db_path))

    expected_tables = {
        _table_name_for(p)
        for folder in (CLEANED_DIR, OUTPUTS_DIR)
        if folder.exists()
        for p in folder.glob("*.csv")
    }

    files_loaded = 0
    rows_loaded = 0
    n, r = load_csvs_from(con, CLEANED_DIR, "cleaned_data")
    files_loaded += n
    rows_loaded += r
    n, r = load_csvs_from(con, OUTPUTS_DIR, "outputs")
    files_loaded += n
    rows_loaded += r

    dropped = _drop_stale_tables(con, expected_tables)
    if dropped:
        log.info("Removed %d stale table(s) with no matching CSV anymore: %s",
                  len(dropped), ", ".join(dropped))

    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.execute(
        f'CREATE OR REPLACE TABLE "{METADATA_TABLE}" AS '
        "SELECT ? AS built_at_utc, ? AS tables_loaded, ? AS total_rows_loaded",
        [built_at, files_loaded, rows_loaded],
    )

    tables = con.execute("SHOW TABLES").fetchall()
    con.close()

    log.info("Done. %d table(s) loaded into %s (%d total rows)", files_loaded, db_path.name, rows_loaded)
    log.info("Tables now available: %s", ", ".join(t[0] for t in tables) if tables else "(none)")
    log.info('Try it: duckdb warehouse/seamark.duckdb -c "SELECT * FROM funnel_summary;"')

    return {
        "tables": sorted(t[0] for t in tables),
        "files_loaded": files_loaded,
        "rows_loaded": rows_loaded,
        "dropped": dropped,
        "built_at_utc": built_at,
    }


def main() -> None:
    build(DB_PATH)


if __name__ == "__main__":
    main()
