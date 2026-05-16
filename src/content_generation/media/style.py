"""Shared image-prompt building blocks used by every channel's prompt builder.

Holds the base brand style line, headline shortening, language→motif lookup,
and topic-blob → imagery heuristics. Per-channel prompt assembly lives in
`channels/<channel>.py` and combines these helpers with channel-specific
composition (square vs tall, stats band, etc.).
"""
from __future__ import annotations

from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation

BRAND = "REPORADAR"

BASE_STYLE = (
    "Bold, high-contrast poster in the visual style of viral tech news graphics. "
    "Deep navy-to-black gradient background with a single dominant glowing element. "
    "Clean iconographic representation. Confident, technical, urgent mood. "
    "No stock-photo people, no fake UI chrome, no lorem ipsum, no extra text beyond "
    "the headline, sub-context, and brand mark. Sans-serif typography, large legible kerning."
)


def headline_from_content(content: GeneratedContent, fallback: str, *, max_len: int = 90) -> str:
    text = (content.hook or content.text or fallback or "").strip()
    return text[:max_len].upper()


def short_summary(summary: str, max_chars: int = 200) -> str:
    return (summary or "").strip().replace("\n", " ")[:max_chars]


_LANGUAGE_MOTIFS = {
    "python": "minimalist serpent ribbon and terminal cursor motif",
    "rust": "geometric gear and crab silhouette motif",
    "go": "gopher silhouette with cloud-network motif",
    "typescript": "stacked TS-monogram cube with bracket motif",
    "javascript": "glowing JS-monogram orb with curly-brace motif",
    "c++": "interlocking circuit-board lattice motif",
    "c": "circuit-board lattice motif",
    "java": "steaming coffee cup with hex-lattice motif",
    "swift": "swallow-bird silhouette with code-bracket motif",
    "kotlin": "stylized K-monogram with orbit lines",
    "ruby": "faceted gemstone with bracket motif",
    "elixir": "amber liquid drop with constellation lines",
    "haskell": "lambda glyph with constellation lines",
    "shell": "terminal prompt with cascading code rain",
}


def imagery_for_repo(evaluation: Evaluation, language: str | None) -> str:
    if language and language.lower() in _LANGUAGE_MOTIFS:
        return _LANGUAGE_MOTIFS[language.lower()]
    summary = (evaluation.summary or "").lower()
    if any(k in summary for k in ("agent", "memory", "rag", "embedding")):
        return "neural lattice with memory-chip silhouette and glowing nodes"
    if any(k in summary for k in ("database", "kv", "store", "sql")):
        return "stacked data-cylinder silhouette with luminous edges"
    if any(k in summary for k in ("model", "llm", "inference", "training")):
        return "orbiting weight-tensor lattice with luminous core"
    if any(k in summary for k in ("video", "image", "render", "graphics", "shader")):
        return "abstract pixel-grid with prismatic light streak"
    if any(k in summary for k in ("network", "proxy", "p2p", "mesh")):
        return "node-graph constellation with glowing connection lines"
    return "abstract code-geometry lattice with luminous focal point"


def imagery_for_hackathon(evaluation: Evaluation, technologies: list[str]) -> str:
    blob = (" ".join(technologies) + " " + (evaluation.summary or "")).lower()
    if any(k in blob for k in ("ar", "vr", "xr", "vision", "spatial")):
        return "translucent spatial-grid floating cube motif"
    if any(k in blob for k in ("agent", "llm", "ai", "model")):
        return "orbiting weight-tensor lattice with luminous core"
    if any(k in blob for k in ("hardware", "robot", "iot", "sensor")):
        return "exploded-view circuit-board silhouette with neon traces"
    if any(k in blob for k in ("game", "unity", "unreal", "graphics")):
        return "abstract pixel-grid with prismatic light streak"
    if any(k in blob for k in ("health", "bio", "medical")):
        return "DNA-helix silhouette with luminous data nodes"
    return "trophy silhouette with confetti light-rays and code-lattice background"
