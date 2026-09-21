# ==
# test_warehouse.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# warehouse/build_duckdb.py claims, in its own header comment, that
# running it any number of times against the same CSVs produces the
# exact same warehouse -- not just non-duplicating, but actually
# convergent, including dropping a table whose CSV no longer exists.
# Same rule as every other test in this project: don't just trust a
# comment, build the warehouse for real, twice, and check.

import hashlib
import sys
from pathlib import Path

import duckdb
import pytest

WAREHOUSE_DIR = Path(__file__).resolve().parent.parent / "warehouse"
sys.path.insert(0, str(WAREHOUSE_DIR))

import build_duckdb  # noqa: E402  (needs the sys.path.insert above first)


def _skip_if_nothing_to_load():
    have_cleaned = any(build_duckdb.CLEANED_DIR.glob("*.csv")) if build_duckdb.CLEANED_DIR.exists() else False
    have_outputs = any(build_duckdb.OUTPUTS_DIR.glob("*.csv")) if build_duckdb.OUTPUTS_DIR.exists() else False
    if not (have_cleaned or have_outputs):
        pytest.skip(
            "Skipping -- no CSVs found in cleaned_data/ or outputs/ yet. "
            "Run `python pipeline.py` first (see the root README's "
            "'Quick start' section for how to do this without real data too)."
        )


# --
# IDEMPOTENCY: two consecutive builds, byte-for-byte the same tables
# --

def _table_checksums(db_path, table_names):
    """One content checksum per table (every column, every row, in a
    fixed sort order) -- a matching row count alone would only prove the
    count stayed stable, not that the rows themselves did.
    """
    con = duckdb.connect(str(db_path))
    checksums = {}
    for table_name in table_names:
        if table_name == build_duckdb.METADATA_TABLE:
            continue  # its own built_at_utc is supposed to change between runs
        df = con.execute(f'SELECT * FROM "{table_name}"').fetchdf()
        sort_cols = list(df.columns) or None
        canonical = df.sort_values(by=sort_cols).reset_index(drop=True) if sort_cols else df
        checksums[table_name] = hashlib.md5(canonical.to_csv(index=False).encode("utf-8")).hexdigest()
    con.close()
    return checksums


def test_two_consecutive_builds_produce_the_same_tables(tmp_path):
    _skip_if_nothing_to_load()
    db_path = tmp_path / "test_warehouse.duckdb"

    first = build_duckdb.build(db_path)
    first_checksums = _table_checksums(db_path, first["tables"])

    second = build_duckdb.build(db_path)
    second_checksums = _table_checksums(db_path, second["tables"])

    # The metadata table's own built_at_utc timestamp is *supposed* to
    # differ between runs -- that's the one legitimate difference. Every
    # actual data table must come out identical, content included, not
    # just the same table names and row counts.
    assert first["tables"] == second["tables"]
    assert first["files_loaded"] == second["files_loaded"]
    assert first["rows_loaded"] == second["rows_loaded"]
    assert first_checksums == second_checksums
    assert len(first_checksums) > 0, "no data tables were found to compare -- test setup issue"


# --
# IDEMPOTENCY: a table with no matching CSV anymore gets dropped, not
# left behind forever
# --

def test_stale_table_is_dropped_on_next_build(tmp_path):
    _skip_if_nothing_to_load()
    db_path = tmp_path / "test_warehouse_stale.duckdb"

    build_duckdb.build(db_path)

    # Simulate a CSV that used to exist (an old stage's output, a file
    # that got renamed) by adding a table build_duckdb didn't create and
    # that matches nothing currently in cleaned_data/ or outputs/.
    con = duckdb.connect(str(db_path))
    con.execute('CREATE OR REPLACE TABLE "leftover_from_a_removed_stage" AS SELECT 1 AS x')
    tables_before = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    con.close()
    assert "leftover_from_a_removed_stage" in tables_before, (
        "test setup itself failed -- the stale table was never created"
    )

    result = build_duckdb.build(db_path)

    assert "leftover_from_a_removed_stage" not in result["tables"]
    assert "leftover_from_a_removed_stage" in result["dropped"]


# --
# A dbt VIEW living in the same database (see dbt_seamark/profiles.yml --
# it reads from this exact seamark.duckdb) must never be touched, even
# when its name matches no CSV. This is the literal scenario that
# crashed a real run once already: the old cleanup logic used SHOW
# TABLES, which lists views too, then tried to DROP TABLE one -- DuckDB
# correctly refuses that, because a view isn't a table, and the whole
# build crashed against the real, dbt-populated seamark.duckdb. This
# only ever surfaced on that real file, never against the throwaway
# databases the other tests in this file build from scratch, since
# those never have a dbt view sitting in them to begin with.
# --

def test_a_dbt_style_view_is_never_touched(tmp_path):
    _skip_if_nothing_to_load()
    db_path = tmp_path / "test_warehouse_view.duckdb"

    build_duckdb.build(db_path)

    # Simulate what dbt_seamark/ actually does to this file: build a
    # VIEW, not a table, with a name that matches no CSV -- the same
    # shape as stg_order_line_items and friends.
    con = duckdb.connect(str(db_path))
    con.execute('CREATE OR REPLACE VIEW "stg_a_dbt_style_view" AS SELECT 1 AS x')
    con.close()

    # Must not raise, and the view must still be exactly what it was.
    result = build_duckdb.build(db_path)

    assert "stg_a_dbt_style_view" not in result["dropped"]
    assert "stg_a_dbt_style_view" not in result["tables"]  # it's a view, not a base table -- correctly absent from this list too

    con = duckdb.connect(str(db_path))
    view_row = con.execute('SELECT x FROM "stg_a_dbt_style_view"').fetchone()
    still_a_view = con.execute(
        "SELECT table_type FROM information_schema.tables WHERE table_name = ?",
        ["stg_a_dbt_style_view"],
    ).fetchone()
    con.close()

    assert view_row == (1,)
    assert still_a_view == ("VIEW",)


# --
# The build's own record of itself is accurate, not just present
# --

def test_metadata_table_matches_what_was_actually_loaded(tmp_path):
    _skip_if_nothing_to_load()
    db_path = tmp_path / "test_warehouse_meta.duckdb"

    result = build_duckdb.build(db_path)

    con = duckdb.connect(str(db_path))
    row = con.execute(
        f'SELECT built_at_utc, tables_loaded, total_rows_loaded FROM "{build_duckdb.METADATA_TABLE}"'
    ).fetchone()
    con.close()

    built_at_utc, tables_loaded, total_rows_loaded = row
    assert built_at_utc is not None and len(built_at_utc) > 0
    assert tables_loaded == result["files_loaded"]
    assert total_rows_loaded == result["rows_loaded"]
    # There's always at least one real CSV in this repo (products_clean.csv
    # and the outputs/*.csv files are committed, non-PII, and always
    # present -- see the root .gitignore), so a healthy build should never
    # report zero rows loaded.
    assert total_rows_loaded > 0
