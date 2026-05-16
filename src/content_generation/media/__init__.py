"""Stage 2 of Content Generation: per-channel image rendering.

Single entry point `render_media(conn, settings, run_id, candidate, evaluation,
content, channel)` resolves the channel profile (size + aspect + prompt builder)
and emits a `RenderResult` with one or more `MediaAsset`s on disk.
"""
from src.content_generation.media.service import render_media

__all__ = ["render_media"]
