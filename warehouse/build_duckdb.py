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
# USAGE:
#   pip install -r requirements.txt   (duckdb is in there)
#   python pipeline.py                (if you haven't already; this
#                                       script only reads what pipeline.py
#                                       already produced, it never
#                                       generates numbers of its own)
#   python warehouse/build_duckdb.py
#
# That leaves warehouse/seamark.duckdb sitting next to this script,
# gitignored, since it is a derived, rebuildable file, not raw data.

import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = PROJECT_ROOT / "cleaned_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DB_PATH = Path(__file__).resolve().parent / "seamark.duckdb"

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


def load_csvs_from(con: duckdb.DuckDBPyConnection, folder: Path, source_label: str) -> int:
    if not folder.exists():
        log.warning("%s does not exist yet, skipping (run pipeline.py first)", folder)
        return 0

    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        log.warning("No CSV files found in %s", folder)
        return 0

    loaded = 0
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

    return loaded


def main() -> None:
    log.info("Building DuckDB warehouse at %s", DB_PATH)
    con = duckdb.connect(str(DB_PATH))

    total = 0
    total += load_csvs_from(con, CLEANED_DIR, "cleaned_data")
    total += load_csvs_from(con, OUTPUTS_DIR, "outputs")

    tables = con.execute("SHOW TABLES").fetchall()
    con.close()

    log.info("Done. %d table(s) loaded into %s", total, DB_PATH.name)
    log.info("Tables now available: %s", ", ".join(t[0] for t in tables) if tables else "(none)")
    log.info('Try it: duckdb warehouse/seamark.duckdb -c "SELECT * FROM funnel_summary;"')


if __name__ == "__main__":
    main()
