"""Selection stage of Candidate Intelligence.

Ranks all evaluated, non-skipped, not-already-posted candidates for a run and
marks the winner with `selected=true`. Writes the `ranking` and `selection`
JSONB sections back onto the candidate row.
"""
from src.candidate_intelligence.selection.ranking import (
    RANKING_VERSION,
    compute_ranking_score,
)
from src.candidate_intelligence.selection.selector import select_top_candidate

__all__ = ["RANKING_VERSION", "compute_ranking_score", "select_top_candidate"]
