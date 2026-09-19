# ==
# conftest.py
# Shared pytest fixtures for the Seamark Project 2 test suite
# ==
#
# Same idea as Project 1's conftest.py — work out the project root
# once and hand every test the folders it needs. Project 2's layout
# is flatter than Project 1's (raw_data/cleaned_data/outputs sit
# directly under the project root instead of inside a Stage1_Analytics
# folder), so the paths below are shorter, but the purpose is the same.

from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def raw_data_dir(project_root):
    return project_root / "raw_data"


@pytest.fixture(scope="session")
def cleaned_data_dir(project_root):
    return project_root / "cleaned_data"


@pytest.fixture(scope="session")
def outputs_dir(project_root):
    return project_root / "outputs"


def skip_if_missing(*paths):
    """A handful of tests need real customer data files -- raw_data/
    orders_export.csv, raw_data/customers_export.csv, and their
    cleaned_data/*_clean.csv derivatives -- which are gitignored on
    purpose (see the root .gitignore and DATA_PROVENANCE.md) since
    they contain real emails and names. That means a fresh clone from
    GitHub, including CI, won't have them, and a test that just tried
    to read them would fail with a confusing FileNotFoundError that
    looks like a real bug. This skips those specific tests instead,
    with a clear reason, rather than either faking the data or letting
    the whole suite look broken on a machine that's never run
    shopify_sync yet.
    """
    missing = [p for p in paths if not p.exists()]
    if missing:
        names = ", ".join(p.name for p in missing)
        pytest.skip(
            f"Skipping -- {names} not present in this checkout. These hold real "
            f"customer data and are gitignored on purpose. Run "
            f"`python shopify_sync/refresh_raw_data.py` then `python pipeline.py` "
            f"locally to generate them, then re-run tests."
        )
