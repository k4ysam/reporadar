from src.candidate_intelligence.selection.ranking import RANKING_VERSION, compute_ranking_score


def _row(overall=8.5, novelty=8, explainability=9, growth=120, audience="developers", already_posted=False):
    return {
        "evaluation": {
            "scores": {
                "overall": overall,
                "novelty": novelty,
                "explainability": explainability,
            },
            "audience": audience,
        },
        "discovery": {"growth_percent": growth},
        "enrichment": {"has_installation_instructions": True, "has_usage_examples": True, "readme": "x"},
        "deduplication": {"already_posted": already_posted},
    }


def test_higher_scores_yield_higher_final():
    a = compute_ranking_score(_row(overall=9, novelty=9, explainability=9, growth=200))
    b = compute_ranking_score(_row(overall=6, novelty=5, explainability=6, growth=20))
    assert a[0] > b[0]


def test_already_posted_applies_penalty():
    score_clean, *_ = compute_ranking_score(_row(already_posted=False))
    score_posted, *_ = compute_ranking_score(_row(already_posted=True))
    assert score_posted < score_clean


def test_freshness_bonus_triggers_above_50pct():
    low_growth, _, _ = compute_ranking_score(_row(growth=10))
    mid_growth, _, _ = compute_ranking_score(_row(growth=60))
    high_growth, _, _ = compute_ranking_score(_row(growth=150))
    assert low_growth < mid_growth < high_growth


def test_ranking_version_is_v2():
    assert RANKING_VERSION == "ranker_v2"


def test_breakdown_records_components():
    _, breakdown, reasons = compute_ranking_score(_row(novelty=9, growth=150))
    assert breakdown.novelty_score == 9
    assert breakdown.freshness_bonus > 0
    # high novelty produces the "Strong novelty" reason
    assert any("novelty" in r.lower() for r in reasons)
