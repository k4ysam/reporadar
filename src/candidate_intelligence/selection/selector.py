"""Selection executor — ranks evaluated candidates and persists the decision.

Sits inside candidate_intelligence because the question "which evaluated
candidate becomes a post?" is the natural closing step of the
"is this project worth featuring?" pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import psycopg

from src.candidate_intelligence.repository import (
    list_evaluated_for_run,
    set_ranking,
    set_selection,
)
from src.candidate_intelligence.selection.ranking import (
    RANKING_VERSION,
    compute_ranking_score,
)
from src.common.ids import selection_id
from src.contracts.selection import RankingBreakdown, SelectionDecision

_log = logging.getLogger(__name__)


def select_top_candidate(
    conn: psycopg.Connection,
    run_id: str,
    *,
    channels: list[str] | None = None,
) -> SelectionDecision | None:
    """Rank all eligible candidates for the run; mark the winner as selected.

    Returns the winning SelectionDecision, or None if no candidate is eligible.
    """
    rows = list_evaluated_for_run(conn, run_id)
    if not rows:
        _log.info("No eligible evaluated candidates in run %s", run_id)
        return None

    total = len(rows)
    scored: list[tuple[float, dict, dict, list[str]]] = []
    for row in rows:
        score, breakdown, reasons = compute_ranking_score(row)
        scored.append((score, row, breakdown.model_dump(mode="json"), reasons))
    scored.sort(key=lambda x: x[0], reverse=True)

    target_channels = channels or ["instagram", "linkedin"]
    winning_decision: SelectionDecision | None = None

    for rank_idx, (score, row, breakdown_dict, reasons) in enumerate(scored, start=1):
        ranking_payload = {
            "ranking_version": RANKING_VERSION,
            "ranking_score": score,
            "rank_in_run": rank_idx,
            "total_candidates_in_run": total,
            "ranked_at": datetime.now(timezone.utc).isoformat(),
            "score_breakdown": breakdown_dict,
            "ranking_reasons": reasons,
        }
        set_ranking(conn, candidate_id=row["id"], ranking_payload=ranking_payload)

        is_winner = rank_idx == 1
        decision = SelectionDecision(
            selection_id=selection_id(),
            candidate_id=row["id"],
            project_id=row["project_id"],
            run_id=run_id,
            ranking_version=RANKING_VERSION,
            ranking_score=score,
            rank_in_run=rank_idx,
            total_candidates_in_run=total,
            score_breakdown=RankingBreakdown(**breakdown_dict),
            ranking_reasons=reasons,
            eligible=True,
            selected=is_winner,
            selected_for_channels=target_channels if is_winner else [],
            selected_at=datetime.now(timezone.utc) if is_winner else None,
            not_selected_reason=None if is_winner else "Outranked by higher-scoring candidate.",
        )
        set_selection(
            conn,
            candidate_id=row["id"],
            selection_payload=decision.model_dump(mode="json"),
        )
        if is_winner:
            winning_decision = decision

    return winning_decision
