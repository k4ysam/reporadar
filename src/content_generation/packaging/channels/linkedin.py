from __future__ import annotations

from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset


def validate_linkedin_package(content: GeneratedContent, media: list[MediaAsset]) -> list[str]:
    issues: list[str] = []
    if content.character_count < 600:
        issues.append(
            f"LinkedIn commentary is short ({content.character_count} chars). "
            "Target 900-1800 chars per channel profile."
        )
    if content.character_count > 3000:
        issues.append(f"LinkedIn commentary exceeds 3000 chars ({content.character_count}).")
    if not media:
        issues.append("LinkedIn package recommends a poster image.")
    for asset in media:
        if not asset.alt_text:
            issues.append(f"LinkedIn poster {asset.asset_id} missing alt text.")
    return issues
