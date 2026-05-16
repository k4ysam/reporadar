"""Smoke tests for the top-level Candidate Intelligence entry points."""
from src.candidate_intelligence import (
    discover_and_evaluate,
    discover_evaluate_and_select,
    evaluate_pending_candidates,
    select_top_candidate,
)


def test_combined_entry_points_are_exported():
    for fn in (
        discover_and_evaluate,
        discover_evaluate_and_select,
        evaluate_pending_candidates,
        select_top_candidate,
    ):
        assert callable(fn)


def test_selection_is_a_submodule_of_candidate_intelligence():
    import src.candidate_intelligence.selection as sel

    assert hasattr(sel, "select_top_candidate")
    assert hasattr(sel, "compute_ranking_score")
    assert sel.RANKING_VERSION == "ranker_v2"
