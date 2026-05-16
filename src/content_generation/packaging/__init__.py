"""Stage 3 of Content Generation: post-package assembly + validation.

Combines text + media + source links into a `PostPackage(status="ready_for_review")`.
Per-channel validators live under `channels/`. The packaging service does
not call out to any LLM or image API — it's pure assembly.
"""
from src.content_generation.packaging.service import build_post_package

__all__ = ["build_post_package"]
