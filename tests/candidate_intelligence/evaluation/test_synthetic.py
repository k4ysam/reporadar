"""Tests for synthesize_evaluation_for_manual.

Manual submission must produce an `Evaluation` with sensible `summary` /
`why_interesting` / `audience` fields for the Content Generation prompts,
without any LLM call.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.candidate_intelligence.evaluation import synthesize_evaluation_for_manual
from src.candidate_intelligence.evaluation.synthetic import _first_useful_paragraph
from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    GithubSnapshot,
    HackathonSnapshot,
    RepoEnrichment,
)


def _source(stype="manual_submission", url="https://example.com") -> CandidateSource:
    return CandidateSource(
        source_type=stype,
        source_name="operator_paste",
        source_url=url,
        discovered_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
    )


def _github_candidate(description: str | None, readme: str | None = None) -> Candidate:
    gh = GithubSnapshot(
        owner="example",
        repo="x",
        full_name="example/x",
        url="https://github.com/example/x",
        description=description,
    )
    return Candidate(
        candidate_id="cand_1",
        project_id="proj_1",
        canonical_repo_key="github:example/x",
        run_id="run_1",
        source=_source(),
        github=gh,
        enrichment=RepoEnrichment(readme=readme) if readme is not None else None,
    )


def test_synthetic_eval_has_default_scores_of_nine():
    candidate = _github_candidate(description="A cool tool")
    ev = synthesize_evaluation_for_manual(candidate)
    assert ev.scores.novelty == 9
    assert ev.scores.explainability == 9
    assert ev.scores.overall == 9.0
    assert ev.skip is False
    assert ev.provider == "operator"
    assert ev.model == "manual"


def test_synthetic_eval_uses_github_description_as_summary():
    candidate = _github_candidate(description="A cool tool")
    ev = synthesize_evaluation_for_manual(candidate)
    assert "A cool tool" in ev.summary
    assert ev.audience == "developers"


def test_synthetic_eval_falls_back_when_no_description():
    candidate = _github_candidate(description=None)
    ev = synthesize_evaluation_for_manual(candidate)
    assert "example/x" in ev.summary


def test_synthetic_eval_augments_with_readme_paragraph():
    readme = (
        "# example/x\n\n"
        "[![CI](badge.svg)](ci)\n\n"
        "This is a real prose paragraph that explains what the project actually does. "
        "It should be picked up as the editorial signal.\n\n"
        "## Installation\n\n```bash\npip install x\n```\n"
    )
    candidate = _github_candidate(description=None, readme=readme)
    ev = synthesize_evaluation_for_manual(candidate)
    assert "real prose paragraph" in ev.summary


def test_first_useful_paragraph_skips_headings_and_badges():
    readme = (
        "# Title\n\n"
        "[![Build](badge.svg)]\n\n"
        "## Subtitle\n\n"
        "Genuine paragraph of forty-plus characters describing the project well."
    )
    p = _first_useful_paragraph(readme)
    assert p.startswith("Genuine paragraph")


def test_first_useful_paragraph_returns_empty_when_nothing_useful():
    readme = "# Title\n\n[![Build](badge.svg)]\n\n# Another\n\nshort"
    assert _first_useful_paragraph(readme) == ""


def test_synthetic_eval_handles_hackathon_candidate():
    h = HackathonSnapshot(
        devpost_url="https://devpost.com/software/x",
        project_name="X Project",
        tagline="A clever hackathon tagline",
    )
    candidate = Candidate(
        candidate_id="cand_h",
        project_id="proj_h",
        canonical_repo_key="devpost:x",
        run_id="run_1",
        source=_source(stype="manual_submission", url=h.devpost_url),
        hackathon=h,
    )
    ev = synthesize_evaluation_for_manual(candidate)
    assert ev.summary == "A clever hackathon tagline"
    assert "hackathon" in ev.audience
