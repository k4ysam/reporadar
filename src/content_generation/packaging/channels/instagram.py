from __future__ import annotations

from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset


def validate_instagram_package(content: GeneratedContent, media: list[MediaAsset]) -> list[str]:
    issues: list[str] = []
    if content.character_count > 2200:
        issues.append(f"Instagram caption exceeds 2200 chars ({content.character_count}).")
    if not media:
        issues.append("Instagram package requires at least one image.")
    if len(content.hashtags) < 3:
        issues.append("Instagram package recommends at least 3 hashtags.")
    if len(content.hashtags) > 8:
        issues.append("Instagram package recommends at most 8 hashtags.")
    return issues
