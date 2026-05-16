from __future__ import annotations

from src.ai_gateway.llm.base import LLMProvider
from src.content_generation.text.channels.instagram import generate_instagram_caption
from src.content_generation.text.channels.linkedin import generate_linkedin_commentary
from src.contracts.candidate import Candidate
from src.contracts.content import Channel, GeneratedContent
from src.contracts.evaluation import Evaluation


def generate_text(
    candidate: Candidate,
    evaluation: Evaluation,
    provider: LLMProvider,
    *,
    channel: Channel,
) -> GeneratedContent:
    """Per v2 §6: `generate_text(project, evaluation, channel)`.

    Dispatches to the per-channel template. Adding a channel = adding a new
    module under `text/channels/` and a new branch here.
    """
    if channel == "instagram":
        return generate_instagram_caption(candidate, evaluation, provider)
    if channel == "linkedin":
        return generate_linkedin_commentary(candidate, evaluation, provider)
    raise NotImplementedError(f"Text generation not implemented for channel {channel!r}")
