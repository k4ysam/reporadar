from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import Candidate, Evaluation, LinkedInPostPackage, PipelineRun


def make_candidate(**overrides):
    base = dict(
        repo_id=1,
        full_name="owner/repo",
        stars_now=500,
        stars_48h_ago=100,
        growth_pct=400.0,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return Candidate(**base)


def make_evaluation(**overrides):
    base = dict(
        repo_id=1,
        full_name="owner/repo",
        summary="A cool tool.",
        why_interesting="It solves X.",
        audience="Developers",
        novelty_score=8.0,
        explainability_score=9.0,
        overall_score=8.5,
        stars_48h=400,
        growth_pct=400.0,
    )
    base.update(overrides)
    return Evaluation(**base)


class TestCandidate:
    def test_round_trip(self):
        c = make_candidate()
        assert Candidate.model_validate(c.model_dump()) == c

    def test_frozen(self):
        c = make_candidate()
        with pytest.raises(Exception):
            c.full_name = "other/repo"  # type: ignore[misc]

    def test_optional_fields(self):
        c = make_candidate(description=None, language=None)
        assert c.description is None
        assert c.language is None

    def test_topics_default_empty(self):
        c = make_candidate()
        assert c.topics == []


class TestEvaluation:
    def test_round_trip(self):
        e = make_evaluation()
        assert Evaluation.model_validate(e.model_dump()) == e

    def test_frozen(self):
        e = make_evaluation()
        with pytest.raises(Exception):
            e.summary = "changed"  # type: ignore[misc]

    def test_score_too_high(self):
        with pytest.raises(ValidationError):
            make_evaluation(novelty_score=11.0)

    def test_score_too_low(self):
        with pytest.raises(ValidationError):
            make_evaluation(overall_score=0.5)

    def test_score_boundaries(self):
        e = make_evaluation(novelty_score=1.0, explainability_score=10.0, overall_score=5.5)
        assert e.novelty_score == 1.0


class TestLinkedInPostPackage:
    def test_round_trip(self):
        package = LinkedInPostPackage(
            commentary="Post text.",
            image_paths=["/tmp/poster.jpg"],
            alt_text="Poster alt text.",
            repo_url="https://github.com/owner/repo",
            source_name="owner/repo",
        )

        assert LinkedInPostPackage.model_validate(package.model_dump()) == package

    def test_image_paths_default_empty(self):
        package = LinkedInPostPackage(
            commentary="Post text.",
            alt_text="Poster alt text.",
            repo_url="https://github.com/owner/repo",
            source_name="owner/repo",
        )

        assert package.image_paths == []

    def test_frozen(self):
        package = LinkedInPostPackage(
            commentary="Post text.",
            alt_text="Poster alt text.",
            repo_url="https://github.com/owner/repo",
            source_name="owner/repo",
        )

        with pytest.raises(Exception):
            package.commentary = "changed"  # type: ignore[misc]


class TestPipelineRun:
    def test_defaults(self):
        r = PipelineRun()
        assert r.status == "running"
        assert r.run_id
        assert r.started_at

    def test_unique_run_ids(self):
        assert PipelineRun().run_id != PipelineRun().run_id
