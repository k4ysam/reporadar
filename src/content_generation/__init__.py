"""Content Generation service.

Three internal stages, composed top-down:

    text/       — per-channel text (caption, commentary, ...)
    media/      — per-channel image rendering
    packaging/  — assembly + per-channel validation → PostPackage

Each stage has its own `service.py` and a parallel `channels/` directory.
The top-level `generate_post_package(...)` runs all three in order. Individual
stages can be invoked directly (e.g. for "regenerate image only" flows) via
`generate_text`, `render_media`, `build_post_package`.
"""
from src.content_generation.media import render_media
from src.content_generation.packaging import build_post_package
from src.content_generation.service import generate_post_package
from src.content_generation.text import generate_text

__all__ = [
    "generate_post_package",
    "generate_text",
    "render_media",
    "build_post_package",
]
