"""Top-level Content Generation entry point.

Composes the three internal stages — text → media → packaging — for one
channel and returns a ready-for-review PostPackage. The orchestrator calls
this once per selected channel.
"""
from __future__ import annotations

import psycopg

from src.ai_gateway.llm.base import LLMProvider
from src.common.config import Settings
from src.content_generation.media import render_media
from src.content_generation.packaging import build_post_package
from src.content_generation.text import generate_text
from src.contracts.candidate import Candidate
from src.contracts.content import Channel
from src.contracts.evaluation import Evaluation
from src.contracts.package import PostPackage


def generate_post_package(
    conn: psycopg.Connection,
    settings: Settings,
    run_id: str,
    candidate: Candidate,
    evaluation: Evaluation,
    provider: LLMProvider,
    *,
    channel: Channel,
) -> PostPackage:
    """End-to-end Content Generation for one channel.

    Stages:
        1. text/      → GeneratedContent
        2. media/     → RenderResult (one or more MediaAssets on disk)
        3. packaging/ → PostPackage (status="ready_for_review")
    """
    content = generate_text(candidate, evaluation, provider, channel=channel)
    render = render_media(conn, settings, run_id, candidate, evaluation, content, channel=channel)
    return build_post_package(candidate, content, render.assets, run_id=run_id, channel=channel)
