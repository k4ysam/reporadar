"""Synthetic Evaluation for manually-submitted candidates.

Operator submission implicitly approves the project — we don't ask the LLM
"is this worth featuring?". Instead, this module builds a placeholder
`Evaluation` directly from the candidate's existing metadata (+ README when
enrichment ran), so the downstream Content Generation service has the same
editorial fields (`summary`, `why_interesting`, `audience`) it expects from
the real evaluator.

This lets `operator_api.cmd_submit` skip the evaluation phase entirely while
keeping the rest of the pipeline (Content Generation, Publishing) untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.common.ids import evaluation_id
from src.contracts.candidate import Candidate
from src.contracts.evaluation import Evaluation, EvaluationScores

PROMPT_VERSION = "manual_submission_v1"


def synthesize_evaluation_for_manual(candidate: Candidate) -> Evaluation:
    """Build a placeholder Evaluation for a manually-submitted candidate.

    Scores default to 9.0 across the board because operator submission is an
    implicit "feature this" — there's no LLM rubric to apply. The fields the
    Content Generation prompts read (`summary`, `why_interesting`, `audience`)
    are derived from the GitHub description / Devpost tagline, augmented with
    the first useful paragraph of the README when available.
    """
    summary, why, audience = _derive_editorial_fields(candidate)
    return Evaluation(
        evaluation_id=evaluation_id(),
        candidate_id=candidate.candidate_id,
        project_id=candidate.project_id,
        run_id=candidate.run_id,
        evaluated_at=datetime.now(timezone.utc),
        model="manual",
        provider="operator",
        prompt_version=PROMPT_VERSION,
        summary=summary,
        why_interesting=why,
        audience=audience,
        scores=EvaluationScores(novelty=9, explainability=9, overall=9.0),
        skip=False,
        raw_response=None,
    )


def _derive_editorial_fields(candidate: Candidate) -> tuple[str, str, str]:
    if candidate.github:
        gh = candidate.github
        summary = gh.description or f"{gh.full_name} on GitHub."
        # Augment with README excerpt if enrichment ran.
        if candidate.enrichment and candidate.enrichment.readme:
            excerpt = _first_useful_paragraph(candidate.enrichment.readme)
            if excerpt:
                summary = f"{summary} {excerpt}" if gh.description else excerpt
        why = "Manually flagged by an operator as worth featuring."
        audience = "developers"
        return summary, why, audience

    if candidate.hackathon:
        h = candidate.hackathon
        summary = h.tagline or h.description or h.project_name
        why = "Manually flagged hackathon project worth featuring."
        audience = "developers, hackathon builders"
        return summary, why, audience

    return candidate.display_name, "Manually flagged.", "developers"


def _first_useful_paragraph(readme: str, max_chars: int = 400) -> str:
    """Skip markdown headings, badges, and code fences; grab the first paragraph
    that looks like prose so we have real editorial signal."""
    for block in readme.split("\n\n"):
        stripped = block.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "!", "<", "```", "[![", "---", "===")):
            continue
        if len(stripped) < 40:
            continue
        return stripped[:max_chars].replace("\n", " ")
    return ""
