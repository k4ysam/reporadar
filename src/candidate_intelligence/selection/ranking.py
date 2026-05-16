"""Score-with-breakdown ranking (v2 §7).

The legacy `_pick_top_eval` just took max(overall_score). v2 keeps that as the
dominant signal but adds smaller bonuses/penalties and persists the breakdown so
future selections can be audited.
"""
from __future__ import annotations

from src.contracts.selection import RankingBreakdown

RANKING_VERSION = "ranker_v2"


def compute_ranking_score(row: dict) -> tuple[float, RankingBreakdown, list[str]]:
    """Score an evaluated candidate row from candidate_repository_evaluations.

    Returns (final_score, breakdown, reasons).
    """
    evaluation = row.get("evaluation") or {}
    scores = evaluation.get("scores") or {}
    discovery = row.get("discovery") or {}
    enrichment = row.get("enrichment") or {}
    dedup = row.get("deduplication") or {}

    overall = float(scores.get("overall") or 0.0)
    novelty = float(scores.get("novelty") or 0.0)
    explainability = float(scores.get("explainability") or 0.0)
    growth_pct = float(discovery.get("growth_percent") or 0.0)

    freshness_bonus = 0.3 if growth_pct >= 100 else (0.15 if growth_pct >= 50 else 0.0)
    audience_fit_score = 0.4 if (evaluation.get("audience") or "").lower().find("developer") >= 0 else 0.2

    weak_evidence_penalty = 0.0
    if not enrichment.get("has_installation_instructions") and not enrichment.get("has_usage_examples"):
        weak_evidence_penalty = 0.2

    already_posted_penalty = 0.5 if dedup.get("already_posted") else 0.0

    breakdown = RankingBreakdown(
        evaluation_overall_score=overall,
        novelty_score=novelty,
        explainability_score=explainability,
        audience_fit_score=audience_fit_score,
        freshness_bonus=freshness_bonus,
        weak_evidence_penalty=weak_evidence_penalty,
        already_posted_penalty=already_posted_penalty,
    )

    final = (
        0.40 * overall
        + 0.20 * novelty
        + 0.15 * explainability
        + 0.15 * audience_fit_score
        + 0.10 * freshness_bonus
        - weak_evidence_penalty
        - already_posted_penalty
    )

    reasons: list[str] = []
    if novelty >= 8:
        reasons.append("Strong novelty score.")
    if explainability >= 8:
        reasons.append("Clear explanation potential.")
    if growth_pct >= 100:
        reasons.append("High GitHub velocity.")
    if not enrichment.get("readme"):
        reasons.append("README missing — selection penalty applied.")

    return round(final, 4), breakdown, reasons
