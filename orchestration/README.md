# Orchestration — running this pipeline as a real dependency graph

`pipeline.py`, in the project root, runs all ten analytics stages one
after another in a single fixed order. That's genuinely fine at this
project's real size — the whole run finishes in under a minute — but
it's not how a pipeline like this actually gets run once it's not one
person on one laptop anymore. This folder is a second way to run the
exact same ten scripts, unchanged, using [Prefect](https://www.prefect.io/)
to express the real dependencies between them: which stages can run
at the same time because neither needs the other's output, which
stages genuinely have to wait, and what happens on a transient
failure instead of the whole run just dying.

`pipeline.py` isn't being replaced. Both ways of running this stay —
same reasoning as `warehouse/` and `dbt_seamark/` sitting alongside
the plain CSV pipeline instead of instead of it.

## What the dependency graph actually is

Worked out by reading which file each script opens, not guessed from
filenames:

- **Stage 1** (data cleaning) has no dependencies — the only stage
  that reads straight from `raw_data/`.
- **Stages 2, 3, 4, 5 and 7** (classification, funnel, forecast,
  pricing, affiliates) each only need Stage 1's cleaned data. None of
  them reads another one of these five's output, so this flow runs
  them concurrently instead of one at a time. Stage 7 doesn't even
  need Stage 1 — it reads the raw UpPromote export directly.
- **Stage 6** (omnichannel visibility) reads Stage 3's
  `funnel_summary.csv`, so it waits on Stage 3 specifically.
- **Stage 8** (catalogue vs sales mix) needs the `Auto_Category`
  column Stage 2 adds, so it waits on Stage 2.
- **Stage 9** (external category benchmark) reads Stage 8's own
  output file, so it waits on Stage 8 alone.
- **Stage 10** (the pipeline health check) re-checks every output
  every earlier stage wrote — same reason `pipeline.py`'s own header
  comment already gives for why it runs last there too — so it waits
  on all nine of the others.

## How to run it

```
pip install -r orchestration/requirements.txt
python orchestration/prefect_flow.py
```

That runs the flow directly in your terminal, no server needed, the
same way `pipeline.py` runs directly. To actually see the dependency
graph, the retries, and a run history in Prefect's own UI instead of
only reading terminal output:

```
prefect server start                     # in one terminal, leave running
python orchestration/prefect_flow.py     # in a second terminal
```

then open `http://127.0.0.1:4200` and look under Flow Runs.

## What this doesn't change

The ten `analytics/*.py` scripts themselves are completely untouched.
This layer only decides what order to run them in and how many can
run at once. Every number they produce is exactly as real as it was
running through `pipeline.py`, because it's the literal same code
producing it.

## Being honest about what's and isn't verified here

Every other script in this project was run for real and checked
against its actual output before being called done. This one, I
couldn't run myself — the environment I built it in has no PyPI
access to install Prefect at all (see `shopify_sync/refresh_raw_data.py`'s
own README note for the same kind of honest gap, for the same kind of
reason). What I *did* verify: every stage's real file dependencies,
by grepping each script's own `read_csv`/`read_excel` calls rather
than trusting `pipeline.py`'s header comment (which turned out to be
slightly stale — it claims Stage 4 reads Stage 3's `funnel_summary.csv`,
which isn't actually true in the current code, so that dependency is
deliberately left out here), and that the file compiles cleanly.
Prefect's `task.submit(wait_for=[...])` pattern used here is a stable,
documented part of its API, not something invented for this. Still —
run it for real once, the same way everything else in this project
got run for real once, before trusting the dependency graph above
over your own eyes.
