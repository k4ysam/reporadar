"""Workflow Orchestrator — coordinates the full pipeline run.

Owns: pipeline_runs table, run-level retry logic, idempotency. Calls every
other service via its public entry point — never reaches into another
service's internals.
"""
from src.orchestrator.pipeline import run_pipeline

__all__ = ["run_pipeline"]
