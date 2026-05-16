"""Stage 1 of Content Generation: per-channel text.

Single entry point `generate_text(candidate, evaluation, provider, channel)`
dispatches to the right channel template under `channels/`.
"""
from src.content_generation.text.service import generate_text

__all__ = ["generate_text"]
