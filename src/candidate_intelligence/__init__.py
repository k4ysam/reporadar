"""Candidate Intelligence service.

End-to-end "what should we post next?" pipeline:

    source_adapters  →  enrichment  →  evaluation  →  selection

Owns the `candidate_repository_evaluations` table — no other service writes
to it. Other services interact via the public entry points below.
"""
from src.candidate_intelligence.selection import select_top_candidate
from src.candidate_intelligence.service import (
    discover_and_evaluate,
    discover_evaluate_and_select,
    evaluate_pending_candidates,
)

__all__ = [
    "discover_evaluate_and_select",
    "discover_and_evaluate",
    "evaluate_pending_candidates",
    "select_top_candidate",
]
