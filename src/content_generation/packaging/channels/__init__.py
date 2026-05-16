"""Per-channel validators. Each channel can enforce its own length / hashtag /
media rules. The packaging service dispatches via the VALIDATORS table below.
"""
from typing import Callable

from src.content_generation.packaging.channels.instagram import validate_instagram_package
from src.content_generation.packaging.channels.linkedin import validate_linkedin_package
from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset

Validator = Callable[[GeneratedContent, list[MediaAsset]], list[str]]

VALIDATORS: dict[str, Validator] = {
    "instagram": validate_instagram_package,
    "linkedin": validate_linkedin_package,
}


def validators_for(channel: str) -> Validator:
    return VALIDATORS.get(channel, lambda *_: [])


__all__ = [
    "validate_instagram_package",
    "validate_linkedin_package",
    "VALIDATORS",
    "validators_for",
]
