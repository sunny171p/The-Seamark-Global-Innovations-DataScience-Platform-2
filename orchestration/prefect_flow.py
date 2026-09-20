# ==
# prefect_flow.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# pipeline.py runs all ten stages one after another, in a single fixed
# order, and that's genuinely fine at this project's real size -- the
# whole run takes under a minute. This file exists to show the other
# way a pipeline like this actually gets run once it's not one person
# on one laptop anymore: a real dependency graph instead of a fixed
# list, tasks that retry themselves once on a transient failure
# instead of just dying, and a run history you can look back at
# afterwards instead of only ever reading the tail of a log file.
#
# pipeline.py is NOT being replaced by this. It still works exactly as
# before, still the simplest way to run this locally with nothing
# extra installed. This is a second way to run the same ten scripts,
# unchanged, added on top -- same reasoning as the DuckDB/dbt layer in
# warehouse/ and dbt_seamark/: built to show the shape a bigger version
# of this would need, not because eleven real orders actually need it
# yet.
#
# THE DEPENDENCY GRAPH BELOW IS REAL, NOT DECORATIVE:
# It comes from actually reading which file each of the ten scripts
# opens, not from guessing based on the filenames or from pipeline.py's
# own fixed run order (that order runs everything one at a time
# whether or not a stage actually needs the one before it to finish
# first). Worth being specific about what that means in practice:
#
#   Stage 1 (data cleaning) has no dependencies -- it's the only
#   stage that reads straight from raw_data/.
#
#   Stages 2, 3, 4, 5 and 7 (classification, funnel, forecast,
#   pricing, affiliates) each only need Stage 1's cleaned data on
#   disk -- none of them reads another one of these five's output.
#   Stage 7 doesn't even need Stage 1; it reads the raw UpPromote
#   export directly. That means these five have no real reason to
#   wait on each other, so this flow runs them concurrently instead
#   of forcing them through one at a time the way pipeline.py's fixed
#   list does.
#
#   Stage 6 (omnichannel visibility) reads outputs/funnel_summary.csv,
#   so it waits specifically on Stage 3, not on the other four.
#
#   Stage 8 (catalogue vs sales mix) needs Auto_Category, the column
#   Stage 2 adds to products_clean.csv, so it waits on Stage 2 (and
#   Stage 1, which Stage 2 already depends on).
#
#   Stage 9 (external category benchmark) reads Stage 8's own output
#   file directly, so it waits on Stage 8 alone.
#
#   Stage 10 (the pipeline health check) re-checks every output every
#   earlier stage wrote, exactly like pipeline.py's own header
#   comment already explains for why it runs last there too -- so
#   here it waits on all nine of the others before it starts.
#
# HOW TO RUN IT:
#   pip install -r orchestration/requirements.txt
#   python orchestration/prefect_flow.py
#
# That runs the flow directly, no server needed, same way pipeline.py
# runs directly. To actually see the dependency graph, retries and run
# history in Prefect's own UI instead of only the terminal:
#   prefect server start                     (in one terminal, leave running)
#   python orchestration/prefect_flow.py      (in another terminal)
# then open http://127.0.0.1:4200 and look under Flow Runs.
#
# WHAT THIS DOESN'T CHANGE:
# The ten analytics/*.py scripts themselves are untouched -- this file
# only decides what order to run them in and how many can run at once.
# Every number they produce is exactly as real as it was running
# through pipeline.py, because it's the literal same code producing
# it, just called from here instead.
# ==

import subprocess
import sys
from pathlib import Path

from prefect import flow, task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYTICS_DIR = PROJECT_ROOT / "analytics"


def _run_stage(filename: str) -> None:
    """Runs one analytics script exactly the way pipeline.py does --
    same interpreter, same working directory, same subprocess
    approach -- so behaviour here can never quietly drift from
    behaviour there. Raises on a non-zero exit so Prefect can actually
    tell a real failure apart from a clean run and retry or stop
    accordingly, instead of the whole flow silently carrying on.
    """
    result = subprocess.run(
        [sys.executable, filename],
        cwd=ANALYTICS_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(
            f"{filename} exited with code {result.returncode}:\n{result.stderr[-2000:]}"
        )


# retries=1 with a short delay: a real transient failure (a locked
# file mid-write, a moment of disk contention) gets one automatic
# second chance before this counts as a real failure and the flow
# stops -- pipeline.py has no equivalent of this at all, it fails
# once and that's it.

@task(name="Stage 1 - Data Cleaning", retries=1, retry_delay_seconds=5, log_prints=True)
def stage1_data_cleaning() -> None:
    _run_stage("01_data_cleaning.py")


@task(name="Stage 2 - Product Classification", retries=1, retry_delay_seconds=5, log_prints=True)
def stage2_product_classification() -> None:
    _run_stage("02_product_classification.py")


@task(name="Stage 3 - Funnel Analysis", retries=1, retry_delay_seconds=5, log_prints=True)
def stage3_funnel_analysis() -> None:
    _run_stage("03_funnel_analysis.py")


@task(name="Stage 4 - Forecast vs Actual", retries=1, retry_delay_seconds=5, log_prints=True)
def stage4_forecast_vs_actual() -> None:
    _run_stage("04_forecast_vs_actual.py")


@task(name="Stage 5 - Pricing Integrity", retries=1, retry_delay_seconds=5, log_prints=True)
def stage5_pricing_integrity() -> None:
    _run_stage("05_pricing_integrity.py")


@task(name="Stage 6 - Omnichannel Visibility", retries=1, retry_delay_seconds=5, log_prints=True)
def stage6_omnichannel_visibility() -> None:
    _run_stage("06_omnichannel_visibility.py")


@task(name="Stage 7 - Affiliate Analysis", retries=1, retry_delay_seconds=5, log_prints=True)
def stage7_affiliate_analysis() -> None:
    _run_stage("07_affiliate_analysis.py")


@task(name="Stage 8 - Catalogue vs Sales Mix", retries=1, retry_delay_seconds=5, log_prints=True)
def stage8_catalog_vs_sales_mix() -> None:
    _run_stage("09_catalog_vs_sales_mix.py")


@task(name="Stage 9 - External Category Benchmark", retries=1, retry_delay_seconds=5, log_prints=True)
def stage9_external_category_benchmark() -> None:
    _run_stage("10_external_category_benchmark.py")


# No retry on the health check itself -- if it fails, it means an
# output another stage already finished writing looks wrong, and
# running that same check again a moment later won't change what's
# already sitting on disk.
@task(name="Stage 10 - Pipeline Health Check", retries=0, log_prints=True)
def stage10_pipeline_health() -> None:
    _run_stage("08_pipeline_health.py")


@flow(name="Seamark Project 2 Pipeline", log_prints=True)
def seamark_pipeline_flow() -> None:
    print("Starting Stage 1 -- everything else in this flow depends on its output.")
    s1 = stage1_data_cleaning.submit()

    # These five only need Stage 1's cleaned data on disk. None of
    # them reads another one of these five's output, so there's no
    # real reason to make them wait on each other -- they run
    # concurrently here instead of one at a time.
    s2 = stage2_product_classification.submit(wait_for=[s1])
    s3 = stage3_funnel_analysis.submit(wait_for=[s1])
    s4 = stage4_forecast_vs_actual.submit(wait_for=[s1])
    s5 = stage5_pricing_integrity.submit(wait_for=[s1])
    s7 = stage7_affiliate_analysis.submit()  # doesn't depend on Stage 1 at all

    # Needs outputs/funnel_summary.csv specifically -- Stage 3's file,
    # not just "something from Stage 1 onward".
    s6 = stage6_omnichannel_visibility.submit(wait_for=[s3])

    # Needs the Auto_Category column Stage 2 adds to products_clean.csv.
    s8 = stage8_catalog_vs_sales_mix.submit(wait_for=[s1, s2])

    # Reads Stage 8's own output file directly.
    s9 = stage9_external_category_benchmark.submit(wait_for=[s8])

    # Re-checks every output every earlier stage wrote, so it's the
    # one task that genuinely needs all nine of the others finished
    # first. .result() here (rather than another .submit()) is what
    # makes this flow, and therefore this whole script, actually fail
    # with a non-zero exit code if the health check fails -- the same
    # thing pipeline.py's own sys.exit(1 if fail_count > 0 else 0)
    # does for the plain-script version.
    stage10_pipeline_health.submit(
        wait_for=[s2, s3, s4, s5, s6, s7, s8, s9]
    ).result()

    print("All ten stages finished. Cleaned data: cleaned_data/  CSV/chart out: outputs/")


if __name__ == "__main__":
    seamark_pipeline_flow()
