"""Smoke test for orchestrator wiring.

The pipeline composes every service. We don't have a stubbed Postgres to run
the full workflow in unit tests, but we can at least confirm the module wires
its dependencies without circular-import errors.
"""


def test_pipeline_imports_clean():
    from src.orchestrator.pipeline import run_pipeline

    assert callable(run_pipeline)


def test_scheduler_imports_clean():
    from src.scheduler.daemon import build_scheduler, run_forever

    assert callable(build_scheduler)
    assert callable(run_forever)
