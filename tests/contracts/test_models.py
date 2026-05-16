from datetime import datetime, timezone

import pytest

from src.contracts import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    Evaluation,
    EvaluationScores,
    GithubSnapshot,
    RankingBreakdown,
    SelectionDecision,
)


def _now():
    return datetime(2026, 5, 16, tzinfo=timezone.utc)


def test_scores_enforce_1_to_10():
    with pytest.raises(ValueError):
        EvaluationScores(novelty=0.5, explainability=8, overall=8)
    with pytest.raises(ValueError):
        EvaluationScores(novelty=8, explainability=8, overall=11)


def test_candidate_display_name_prefers_github_full_name():
    src = CandidateSource(
        source_type="github_discovery",
        source_name="github_search_api",
        source_url="https://github.com/example/example",
        discovered_at=_now(),
    )
    gh = GithubSnapshot(
        owner="example",
        repo="example",
        full_name="example/example",
        url="https://github.com/example/example",
    )
    cand = Candidate(
        candidate_id="cand_x",
        project_id="proj_x",
        canonical_repo_key="github:example/example",
        run_id="run_x",
        source=src,
        github=gh,
    )
    assert cand.display_name == "example/example"


def test_evaluation_roundtrips_through_model_dump():
    ev = Evaluation(
        evaluation_id="eval_1",
        candidate_id="cand_1",
        project_id="proj_1",
        run_id="run_1",
        evaluated_at=_now(),
        model="gpt-5",
        provider="openai",
        prompt_version="repo_eval_v5",
        summary="x",
        why_interesting="y",
        audience="developers",
        scores=EvaluationScores(novelty=8, explainability=9, overall=8.5),
    )
    payload = ev.model_dump(mode="json")
    again = Evaluation(**payload)
    assert again == ev


def test_selection_decision_carries_breakdown():
    decision = SelectionDecision(
        selection_id="sel_1",
        candidate_id="cand_1",
        project_id="proj_1",
        run_id="run_1",
        ranking_version="ranker_v2",
        ranking_score=8.42,
        rank_in_run=1,
        total_candidates_in_run=12,
        score_breakdown=RankingBreakdown(evaluation_overall_score=8.5),
        ranking_reasons=["High velocity"],
        selected=True,
        selected_for_channels=["instagram", "linkedin"],
    )
    assert decision.selected
    assert decision.score_breakdown.evaluation_overall_score == 8.5
