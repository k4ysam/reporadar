"""Deterministic prompt builders for OpenAI image generation.

Style target: "stop-scroll headline poster" — single dominant visual,
dark high-contrast background, bold legible headline, small brand mark.
The headline is the caption hook; technical evidence stays in the caption.
"""
from __future__ import annotations

from src.models import Caption, Evaluation, HackathonCandidate

_BRAND = "REPORADAR"

_BASE_STYLE = (
    "Bold, high-contrast Instagram-square poster in the visual style of "
    "viral tech news graphics. Deep navy-to-black gradient background with "
    "a single dominant glowing element. Clean iconographic representation. "
    "Confident, technical, urgent mood. No stock-photo people, no fake UI "
    "chrome, no lorem ipsum, no extra text beyond the headline, sub-context, "
    "and brand mark. Sans-serif typography, large legible kerning."
)


def build_repo_image_prompt(
    evaluation: Evaluation,
    caption: Caption,
    language: str | None = None,
) -> str:
    repo_short = evaluation.full_name.split("/")[-1]
    sub_context_parts = [evaluation.full_name]
    if language:
        sub_context_parts.append(language)
    sub_context = "  ·  ".join(sub_context_parts)

    imagery = _imagery_for_repo(evaluation, language)
    headline = _headline(caption, evaluation.summary)

    return (
        f"{_BASE_STYLE}\n\n"
        f"Imagery: {imagery}. The visual should evoke the project's purpose "
        f"({_short_summary(evaluation.summary)}).\n\n"
        f'Headline (rendered legibly, large, all-caps, sans-serif, top-center): "{headline}"\n'
        f'Sub-context (small, bottom-left, single line): "{sub_context}"\n'
        f'Brand mark (small, bottom-right, single line): "{_BRAND}"\n\n'
        f"Subject hint: open-source project named {repo_short}."
    )


def build_hackathon_image_prompt(
    evaluation: Evaluation,
    candidate: HackathonCandidate,
    caption: Caption,
) -> str:
    sub_context_parts = []
    if candidate.hackathon_name:
        sub_context_parts.append(candidate.hackathon_name)
    if candidate.prize:
        sub_context_parts.append(candidate.prize)
    sub_context = "  ·  ".join(sub_context_parts) or candidate.project_name

    imagery = _imagery_for_hackathon(evaluation, candidate)
    headline = _headline(caption, evaluation.summary)

    return (
        f"{_BASE_STYLE}\n\n"
        f"Hackathon winner spotlight. Imagery: {imagery}. The visual should evoke "
        f"the project's purpose ({_short_summary(evaluation.summary)}).\n\n"
        f'Headline (rendered legibly, large, all-caps, sans-serif, top-center): "{headline}"\n'
        f'Sub-context (small, bottom-left, single line): "{sub_context}"\n'
        f'Brand mark (small, bottom-right, single line): "{_BRAND}"\n\n'
        f"Subject hint: hackathon project named {candidate.project_name}."
    )


def _headline(caption: Caption, fallback: str) -> str:
    text = (caption.hook or fallback or "").strip()
    return text[:90].upper()


def _short_summary(summary: str, max_chars: int = 200) -> str:
    s = (summary or "").strip().replace("\n", " ")
    return s[:max_chars]


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


def _imagery_for_repo(evaluation: Evaluation, language: str | None) -> str:
    if language:
        key = language.lower()
        if key in _LANGUAGE_MOTIFS:
            return _LANGUAGE_MOTIFS[key]
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


def _imagery_for_hackathon(evaluation: Evaluation, candidate: HackathonCandidate) -> str:
    techs = " ".join((candidate.technologies or [])).lower()
    summary = (evaluation.summary or "").lower()
    blob = f"{techs} {summary}"
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
