from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.common.ids import post_instance_id
from src.content_generation.packaging.channels import validators_for
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset
from src.contracts.package import PostPackage

_log = logging.getLogger(__name__)


def build_post_package(
    candidate: Candidate,
    content: GeneratedContent,
    media: list[MediaAsset],
    *,
    run_id: str,
    channel: str,
) -> PostPackage:
    """Combine text + media + source links into a `PostPackage`.

    Runs the per-channel validator and attaches any warnings as `review_notes`
    on the package so the operator can see them in the dashboard.
    """
    issues = validators_for(channel)(content, media)
    for issue in issues:
        _log.warning("Package validation [%s]: %s", channel, issue)

    source_links: list[str] = []
    if candidate.github:
        source_links.append(candidate.github.url)
    if candidate.hackathon:
        source_links.append(candidate.hackathon.devpost_url)
        if candidate.hackathon.github_url:
            source_links.append(candidate.hackathon.github_url)
        if candidate.hackathon.demo_url:
            source_links.append(candidate.hackathon.demo_url)

    return PostPackage(
        post_id=post_instance_id(channel),
        project_id=candidate.project_id,
        candidate_id=candidate.candidate_id,
        run_id=run_id,
        channel=channel,
        status="ready_for_review",
        content=content,
        media=media,
        source_links=source_links,
        review_notes="; ".join(issues) if issues else None,
        created_at=datetime.now(timezone.utc),
    )
