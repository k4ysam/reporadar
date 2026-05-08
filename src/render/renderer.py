from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import Caption, Evaluation, HackathonCandidate, RenderResult

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

INSTAGRAM_SQUARE = (1080, 1080)
LINKEDIN_POSTER = (1200, 1500)


@dataclass
class RepoCardContext:
    repo_full_name: str
    repo_short_name: str
    stars_added: int
    window_hours: int
    growth_pct: float
    summary: str
    language: str | None
    audience: str
    novelty: float
    explainability: float
    overall: float


@dataclass
class HackathonSlideContext:
    project_name: str
    hackathon_name: str | None
    prize: str | None
    tagline: str | None
    summary: str
    why_interesting: str
    technologies: list[str]
    team: str | None
    github_url: str | None
    devpost_url: str
    demo_url: str | None


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def render_html(template_name: str, ctx: dict) -> str:
    env = _env()
    template = env.get_template(template_name)
    static_url = STATIC_DIR.resolve().as_uri() + "/"
    return template.render(static_url=static_url, **ctx)


def _ensure_output_dir(output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _png_to_jpeg(png_path: Path, jpeg_path: Path) -> None:
    """Convert PNG to JPEG. Falls back to renaming if Pillow is unavailable."""
    try:
        from PIL import Image  # type: ignore

        with Image.open(png_path) as im:
            im.convert("RGB").save(jpeg_path, "JPEG", quality=92)
        png_path.unlink(missing_ok=True)
    except ImportError:
        # Pillow missing: keep the PNG bytes but at the path the caller expects.
        # Instagram's Graph API accepts PNG content regardless of file extension.
        png_path.replace(jpeg_path)


def _render_one(html: str, output_path: Path, viewport: tuple[int, int]) -> Path:
    """Render a single HTML doc to a JPEG at output_path using Playwright."""
    from playwright.sync_api import sync_playwright

    png_path = output_path.with_suffix(".png")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=2,
            )
            page = context.new_page()
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=str(png_path), type="png", omit_background=False, full_page=False)
        finally:
            browser.close()

    if output_path.suffix.lower() in (".jpg", ".jpeg"):
        _png_to_jpeg(png_path, output_path)
    else:
        png_path.rename(output_path)
    return output_path


def render_repo_card(
    evaluation: Evaluation,
    caption: Caption,
    output_dir: str | Path,
    *,
    window_hours: int = 72,
    language: str | None = None,
    file_stem: str | None = None,
) -> RenderResult:
    out = _ensure_output_dir(output_dir)
    short = evaluation.full_name.split("/")[-1]
    ctx = {
        "repo_full_name": evaluation.full_name,
        "repo_short_name": short,
        "stars_added": evaluation.stars_48h,
        "window_hours": window_hours,
        "growth_pct": int(evaluation.growth_pct),
        "summary": caption.hook or evaluation.summary,
        "tagline": evaluation.summary,
        "language": language or "",
        "audience": evaluation.audience,
        "novelty": evaluation.novelty_score,
        "explainability": evaluation.explainability_score,
        "overall": evaluation.overall_score,
    }
    html = render_html("repo_card.html", ctx)

    stem = file_stem or _safe_stem(evaluation.full_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out / f"repo_{stem}_{timestamp}.jpg"
    _render_one(html, target, INSTAGRAM_SQUARE)
    return RenderResult(media_type="single", paths=[str(target)])


def render_linkedin_repo_poster(
    evaluation: Evaluation,
    output_dir: str | Path,
    *,
    headline: str,
    language: str | None = None,
    topics: list[str] | None = None,
    window_hours: int = 72,
    file_stem: str | None = None,
) -> RenderResult:
    out = _ensure_output_dir(output_dir)
    short = evaluation.full_name.split("/")[-1]
    owner = evaluation.full_name.split("/")[0] if "/" in evaluation.full_name else ""
    star_label = f"+{evaluation.stars_48h} stars" if evaluation.stars_48h else "tracked on GitHub"
    growth_label = f"+{int(evaluation.growth_pct)}% growth" if evaluation.growth_pct else "rising repo"
    topic_badges = [t for t in (topics or []) if t][:3]
    code_lines = [
        f"git clone https://github.com/{evaluation.full_name}",
        f"repo = '{short}'",
        f"signal = '{star_label}'",
        f"audience = '{evaluation.audience[:42]}'",
    ]
    ctx = {
        "repo_full_name": evaluation.full_name,
        "repo_short_name": short,
        "repo_owner": owner,
        "headline": headline,
        "stars_added": evaluation.stars_48h,
        "star_label": star_label,
        "growth_label": growth_label,
        "window_hours": window_hours,
        "language": language or "",
        "topics": topic_badges,
        "summary": evaluation.summary,
        "why_interesting": evaluation.why_interesting,
        "code_lines": code_lines,
    }
    html = render_html("linkedin_repo_poster.html", ctx)

    stem = file_stem or _safe_stem(evaluation.full_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out / f"linkedin_repo_{stem}_{timestamp}.jpg"
    _render_one(html, target, LINKEDIN_POSTER)
    return RenderResult(media_type="single", paths=[str(target)])


def render_hackathon_carousel(
    evaluation: Evaluation,
    candidate: HackathonCandidate,
    caption: Caption,
    output_dir: str | Path,
    *,
    file_stem: str | None = None,
) -> RenderResult:
    out = _ensure_output_dir(output_dir)
    base_ctx = {
        "project_name": candidate.project_name,
        "hackathon_name": candidate.hackathon_name,
        "prize": candidate.prize,
        "tagline": candidate.tagline,
        "summary": evaluation.summary,
        "why_interesting": evaluation.why_interesting,
        "technologies": candidate.technologies[:8],
        "team": candidate.team,
        "github_url": candidate.github_url,
        "devpost_url": candidate.devpost_url,
        "demo_url": candidate.demo_url,
        "hook": caption.hook,
        "body": caption.body,
        "cta": caption.cta,
    }

    slide_templates = [
        "hackathon_slide_1.html",
        "hackathon_slide_2.html",
        "hackathon_slide_3.html",
        "hackathon_slide_4.html",
    ]
    stem = file_stem or _safe_stem(candidate.project_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    paths: list[str] = []
    for i, tpl in enumerate(slide_templates, start=1):
        html = render_html(tpl, base_ctx)
        target = out / f"hackathon_{stem}_{timestamp}_{i}.jpg"
        _render_one(html, target, INSTAGRAM_SQUARE)
        paths.append(str(target))

    return RenderResult(media_type="carousel", paths=paths)


def _safe_stem(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in name).strip("-").lower()
    return safe[:60] or "post"
