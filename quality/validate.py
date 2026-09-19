# ==
# validate.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# Runs the schemas in schemas.py against whatever's currently sitting
# in cleaned_data/. This is meant to run after `python pipeline.py`,
# as a quick second check that the shape of the output is still what
# every downstream script expects, on top of the test suite's own
# number-correctness checks.
#
# USAGE:
#   python pipeline.py            (if you haven't already)
#   python quality/validate.py
#
# A clean run prints one OK line per file and exits 0. A schema
# failure prints which file, which column, and what rule failed,
# without ever printing the actual row values for orders_clean.csv or
# customers_clean.csv, since those can carry a real customer's data
# (see schemas.py's own note on this for orders_clean specifically).

import logging
import sys
from pathlib import Path

import pandas as pd
import pandera.errors

from schemas import SCHEMAS_BY_FILENAME

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = PROJECT_ROOT / "cleaned_data"

# Files whose validation failures should never print row contents to
# the console, since a failure could otherwise dump a real customer's
# name or email straight into a terminal or a CI log.
SENSITIVE_FILES = {"orders_clean.csv", "customers_clean.csv"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("validate")


def validate_file(filename: str, schema) -> bool:
    path = CLEANED_DIR / filename
    if not path.exists():
        log.warning("%s not found, skipping (run pipeline.py first)", filename)
        return True

    df = pd.read_csv(path)
    try:
        schema.validate(df, lazy=True)
    except pandera.errors.SchemaErrors as exc:
        if filename in SENSITIVE_FILES:
            failed_columns = sorted(set(exc.failure_cases["column"].dropna().tolist()))
            log.error(
                "%s FAILED schema validation on column(s): %s "
                "(row values withheld, this file can carry real customer data)",
                filename, ", ".join(failed_columns) or "unknown",
            )
        else:
            log.error("%s FAILED schema validation:\n%s", filename, exc.failure_cases.to_string())
        return False

    log.info("%-30s OK  (%d rows validated against %d rules)", filename, len(df), len(schema.columns))
    return True


def main() -> int:
    all_ok = True
    for filename, schema in SCHEMAS_BY_FILENAME.items():
        ok = validate_file(filename, schema)
        all_ok = all_ok and ok

    if all_ok:
        log.info("All schemas passed.")
        return 0

    log.error("One or more files failed schema validation. See above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
