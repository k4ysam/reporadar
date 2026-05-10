# LinkedIn-First Evolving AI Style Implementation Plan

## Overview

Update RepoRadar to generate LinkedIn-first posts inspired by Evolving AI's image-and-copy strategy.

The immediate deliverable is not a database migration or a new publishing system. It is a repeatable LinkedIn post package:

1. Long-form LinkedIn commentary in the Evolving AI structure.
2. A LinkedIn-ready image asset attached to the post.
3. Alt text for the image.
4. The repo URL and source metadata needed for review or later API publishing.

The first implementation should target manual review/export. Direct LinkedIn API publishing can come after credentials, author type, and posting permissions are confirmed.

## Current State Analysis

RepoRadar already has deterministic image rendering. It does **not** currently use AI image generation. `src/render/renderer.py` renders Jinja HTML into JPEGs with Playwright (`src/render/renderer.py:82-104`). Repo images are created by `render_repo_card(...)` (`src/render/renderer.py:107-138`) and use `repo_card.html` (`src/render/templates/repo_card.html:1-34`). Current repo cards are Instagram-square `1080x1080` (`src/render/renderer.py:15`) and show:

- "RISING ON GITHUB" kicker.
- Repo short name.
- Owner.
- Star/growth/language stats.
- Summary/tagline.
- Audience.

The existing caption generator is still Instagram-oriented. It asks for short captions, <=500-char bodies, one CTA, and hashtags (`src/caption/generator.py:9-29`). That is not the right shape for LinkedIn, where Evolving AI's working pattern is longer text plus an image that acts like a headline poster.

## Evolving AI LinkedIn Image Analysis

Observed public Evolving AI LinkedIn images:

- Apple/Q.ai post image: dark monochrome AI/human portrait, Apple/Q.ai logo badges, small "EVOLVING AI" brand divider, and a huge all-caps headline: "APPLE BUYS SECRETIVE ISRAELI STARTUP Q.AI..." Source image from LinkedIn media: `media.licdn.com/...D4E22AQGMIQdCrNxvaA...`.
- Anthropic consciousness post image: close-up human portrait, Anthropic/Claude badges, small "EVOLVING AI" brand divider, and a huge all-caps headline: "ANTHROPIC CEO WARNS..." Source image from LinkedIn media: `media.licdn.com/...D4E22AQH99GDDGrppng...`.
- Interactive "Can you spot the AI videos?" post: the copy and media ask the reader to judge whether examples are real or AI-generated, driving comments through a simple challenge.

### Visual Pattern

Evolving AI images are not illustrations for detail. They are stop-scroll headline posters:

- One dominant visual subject: person, company, AI object, or conceptual scene.
- Very dark or high-contrast background.
- Strong brand/icon anchors: Apple, Anthropic, Claude, AI/circuit motifs.
- Large all-caps white headline occupying the bottom third to half of the image.
- Minimal secondary text.
- Small brand mark near the headline divider.
- The image communicates the core claim before the user reads the caption.

### Why It Attracts Viewers

The image does three jobs:

1. **Immediate comprehension**: the viewer understands the post topic in under a second.
2. **Curiosity gap**: the image states a surprising claim but leaves the explanation to the caption.
3. **Comment bait with substance**: the post text asks "What are your thoughts?" or creates a guessing game, which gives readers a low-friction reason to reply.

The caption then rewards the click/stop with context, mechanism, proof, caveat, and implication.

## RepoRadar Visual Strategy

RepoRadar should not copy Evolving AI's AI-news aesthetic exactly. It should copy the system:

> Image = sharp claim. Caption = technical evidence.

### Primary Visual Format: Repo Poster

For each repo, generate one LinkedIn image that looks like a technical headline poster.

Required elements:

- Kicker: `RISING ON GITHUB` or `REPO RADAR`.
- Huge headline: a claim about what the repo does.
- Repo identity: `owner/repo`.
- Proof strip: `+{stars} stars`, `{window_hours}h`, `{language}`, optional license/topic.
- Visual anchor: code/product screenshot if available; otherwise a generated abstract code-system visual using CSS, not AI image generation.
- Brand: `RepoRadar`.

Example image headline:

```text
A 4-DAY-OLD REPO IS TURNING LOCAL FILES INTO AGENT MEMORY
```

Supporting strip:

```text
owner/repo - +1,240 stars in 48h - Python - MIT
```

### Secondary Visual Format: Build Challenge

For hackathon or demo projects:

```text
WOULD YOU SHIP THIS AFTER 36 HOURS?
```

Supporting strip:

```text
ProjectName - Hackathon winner - React + Python + WebRTC
```

This copies the interaction mechanic from Evolving AI's "Can you spot..." style: the image asks the viewer to judge, while the caption explains.

### Visual Tone

Use:

- Dark, high-contrast backgrounds.
- Large white uppercase headline.
- Small orange/green/blue accent badges.
- Code grid, terminal, dependency graph, repo file tree, or product screenshot motifs.
- Less text than the current repo card tagline area.

Avoid:

- Generic AI-generated stock art.
- Overly polished SaaS hero graphics.
- Tiny text that cannot be read in-feed.
- Claims that sound more certain than the repo evidence supports.

## LinkedIn Copy Strategy

Generate commentary separately from the existing Instagram caption.

LinkedIn post structure:

```text
[Hook] [Repo/project] just [specific surprising capability].

[Context: what it is, who built it if known, why now.]

[Mechanism: how it works in plain technical language.]

[Proof: stars, growth, commits, README, demo, benchmark, language, license.]

The caveat: [what is early, unverified, missing, or rough.]

What stands out is [the bigger developer-workflow implication].

Would you use this in your stack?

Follow RepoRadar to catch new repos before they go mainstream.
```

Hashtags should be minimal on LinkedIn: 3-5 max.

Example:

```text
MemPalace is turning AI memory into a local file system.

Most AI memory tools hide the retrieval layer behind a hosted product. This repo takes the opposite route: store conversations locally, organize them into a memory-palace hierarchy, then retrieve through SQLite and vector search.

The reason developers are paying attention is simple: coding agents forget the context that makes them useful. A local, inspectable memory layer gives builders something they can debug, move, and own.

The caveat: benchmark claims still need independent reproduction, and memory systems only work if retrieval stays clean over time.

What stands out is the direction. AI memory is moving from product feature to developer infrastructure.

Would you trust this with your coding context?

Follow RepoRadar to catch new repos before they go mainstream.

#opensource #github #devtools #aiagents
```

## Desired End State

The pipeline can produce a `LinkedInPostPackage` for a repo:

```python
class LinkedInPostPackage(BaseModel):
    commentary: str
    image_paths: list[str]
    alt_text: str
    repo_url: str
    source_name: str
```

This object can be saved locally, printed by CLI, shown in dashboard, or later passed into a LinkedIn API publisher.

No SQLite schema changes are required for the first implementation.

## Design Decisions

### No New Database Fields

Do not add `freshness_angle`, `mechanism`, `proof_points`, or `caveat` columns.

Reason: LinkedIn copy can be generated at package time from the existing `Evaluation`, `Candidate`, and fetched repo context. Persisting extra fields is useful later, but unnecessary for the first LinkedIn target.

### Keep Existing Image Renderer, Add LinkedIn Variant

Keep `render_repo_card(...)` for existing Instagram output. Add a LinkedIn-specific poster renderer instead of replacing current behavior.

Recommended new function:

```python
render_linkedin_repo_poster(...)
```

Recommended template:

```text
src/render/templates/linkedin_repo_poster.html
```

Recommended dimensions:

```python
LINKEDIN_POSTER = (1200, 1500)
```

Why 1200x1500: Evolving AI images are portrait-oriented and headline-heavy. A taller image gives space for visual subject plus large headline. LinkedIn accepts image posts and displays portrait images prominently in-feed.

### No AI Image Generation In V1

Do not generate bitmap art with an AI image model in the first implementation.

Use CSS/HTML visuals:

- Terminal panel.
- Repo file tree.
- Dependency graph lines.
- Code-token grid.
- GitHub-style metric badges.

Reason: generated AI art can look generic and untrusted on LinkedIn. RepoRadar's authority should come from technical specificity.

### LinkedIn API Later

Direct publishing requires LinkedIn app credentials, an author URN, approved permissions, and image upload flow. Official LinkedIn docs state that image posts require uploading an image to obtain an `urn:li:image:{id}`, then creating a post with that image asset. MultiImage organic posts are supported, while organic carousel posts are not.

Sources:

- LinkedIn Posts API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-04
- LinkedIn Images API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api?view=li-lms-2026-04
- LinkedIn MultiImage API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/multiimage-post-api?view=li-lms-2026-04

## What We're NOT Doing

- No database migration.
- No new evaluation schema.
- No automatic LinkedIn publishing in the first slice.
- No Instagram redesign.
- No newsletter generation.
- No AI image generation model.
- No multi-image carousel for organic LinkedIn in V1.

## Implementation Approach

Build a LinkedIn package layer next to the existing Instagram caption/render path:

1. Add LinkedIn commentary generation.
2. Add LinkedIn repo poster rendering.
3. Add a package builder that combines commentary, image path, alt text, and repo URL.
4. Add CLI/manual review output.
5. Add tests.

---

## Phase 1: Add LinkedIn Post Package Model And Generator

### Overview

Create a LinkedIn-specific content package without changing existing caption or DB behavior.

### Changes Required

#### 1. Add LinkedIn Package Model

**File**: `src/models.py`

**Changes**:

Add:

```python
class LinkedInPostPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    commentary: str
    image_paths: list[str] = Field(default_factory=list)
    alt_text: str
    repo_url: str
    source_name: str
```

#### 2. Add LinkedIn Commentary Generator

**File**: `src/caption/linkedin.py`

**Changes**:

Create:

```python
def generate_repo_linkedin_commentary(
    evaluation: Evaluation,
    provider: LLMProvider,
    *,
    repo_url: str,
    language: str | None = None,
    topics: list[str] | None = None,
) -> str:
    ...
```

Prompt requirements:

- 900-1800 characters.
- No more than 3-5 hashtags.
- Opens with the repo/project and specific capability.
- Includes proof available from existing fields: stars, growth, language, summary, why interesting.
- Includes a caveat using safe phrasing if evidence is thin.
- Ends with a comment-driving question.
- Does not invent benchmark numbers, licenses, companies, or claims.

### Success Criteria

- [ ] Generator returns text, not a `Caption`, because LinkedIn commentary does not need hook/body/cta separation.
- [ ] Unit tests verify the provider prompt includes repo URL, stars, growth, summary, why interesting, and LinkedIn-specific constraints.
- [ ] Retry behavior exists for empty/invalid output if the implementation chooses structured JSON; if plain text, test that empty output raises or retries.

---

## Phase 2: Add LinkedIn Repo Poster Renderer

### Overview

Create a portrait LinkedIn image template inspired by Evolving AI's headline poster pattern.

### Changes Required

#### 1. Renderer Constant And Function

**File**: `src/render/renderer.py`

**Changes**:

Add:

```python
LINKEDIN_POSTER = (1200, 1500)
```

Add:

```python
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
    ...
```

This should call `_render_one(html, target, LINKEDIN_POSTER)`.

#### 2. New Template

**File**: `src/render/templates/linkedin_repo_poster.html`

**Changes**:

Build layout:

```html
<div class="linkedin-poster">
  <div class="poster-visual">
    <div class="terminal-window">...</div>
    <div class="repo-node-map">...</div>
  </div>

  <div class="poster-brand-rule">
    <span>REPORADAR</span>
  </div>

  <h1 class="poster-headline">{{ headline }}</h1>

  <div class="poster-proof-strip">
    <span>{{ repo_full_name }}</span>
    <span>+{{ stars_added }} stars</span>
    <span>{{ window_hours }}h</span>
    {% if language %}<span>{{ language }}</span>{% endif %}
  </div>
</div>
```

#### 3. CSS

**File**: `src/render/static/style.css`

**Changes**:

Add LinkedIn poster styles:

- 1200x1500 layout.
- Dark background.
- Upper visual area.
- Bottom black headline block.
- Large white uppercase headline.
- Small brand divider.
- Proof badges.
- Text sizes that remain readable in feed.

Keep the existing Instagram card styles unchanged.

### Success Criteria

- [ ] Renderer tests mock Playwright and verify `render_linkedin_repo_poster` returns a single image path.
- [ ] Rendered HTML contains headline, repo name, stars, and brand.
- [ ] Existing repo/hackathon renderer tests still pass.

---

## Phase 3: Build LinkedIn Package From Existing Pipeline Objects

### Overview

Combine generated commentary and poster image into one reviewable object.

### Changes Required

#### 1. Package Builder

**File**: `src/linkedin/package.py`

**Changes**:

Create:

```python
def build_repo_linkedin_package(
    evaluation: Evaluation,
    provider: LLMProvider,
    output_dir: str | Path,
    *,
    language: str | None = None,
    topics: list[str] | None = None,
    window_hours: int = 72,
) -> LinkedInPostPackage:
    ...
```

Flow:

1. Derive `repo_url = f"https://github.com/{evaluation.full_name}"`.
2. Generate commentary.
3. Generate or derive image headline.
4. Render LinkedIn repo poster.
5. Return `LinkedInPostPackage`.

#### 2. Headline Builder

**File**: `src/linkedin/package.py`

**Changes**:

Add a deterministic fallback:

```python
def build_repo_poster_headline(evaluation: Evaluation) -> str:
    return f"{evaluation.full_name.split('/')[-1]} is rising fast on GitHub"
```

Optionally allow the LLM generator to return a headline later, but keep V1 deterministic or derived from `Caption.hook`/`evaluation.summary`.

#### 3. Alt Text Builder

**File**: `src/linkedin/package.py`

**Changes**:

Add:

```python
def build_repo_alt_text(evaluation: Evaluation, headline: str) -> str:
    return (
        f"RepoRadar poster for {evaluation.full_name}. "
        f"Headline: {headline}. "
        f"Shows {evaluation.stars_48h} stars added and {int(evaluation.growth_pct)} percent growth."
    )
```

### Success Criteria

- [ ] Unit tests assert package includes commentary, image path, alt text, repo URL, and `source_name`.
- [ ] Package builder does not write to the database.
- [ ] Package builder uses existing evaluation fields only.

---

## Phase 4: CLI Or Manual Review Command

### Overview

Expose LinkedIn package generation without posting directly.

### Changes Required

#### 1. CLI Command

**File**: `src/cli.py`

**Changes**:

Add a command such as:

```bash
python -m src linkedin-preview
```

Possible behavior:

- Select the latest rendered/evaluated repo post.
- Build LinkedIn package.
- Print commentary.
- Print image path.
- Print alt text.

If selecting latest evaluation is awkward, add a lower-level function first and wire CLI in a later pass.

#### 2. Optional Output File

**File**: CLI implementation

**Changes**:

Optionally write a JSON sidecar to `OUTPUT_DIR`:

```text
linkedin_owner-repo_YYYYMMDD-HHMMSS.json
```

Fields:

- `commentary`
- `image_paths`
- `alt_text`
- `repo_url`
- `source_name`

This is not a DB migration and keeps review artifacts colocated with images.

### Success Criteria

- [ ] CLI command can generate a LinkedIn package for a mocked/latest repo evaluation.
- [ ] Output includes everything needed to manually post on LinkedIn.
- [ ] No LinkedIn network call occurs.

---

## Phase 5: Optional LinkedIn API Publisher Later

### Overview

Only implement after the manual package is working and LinkedIn credentials/permissions are available.

### Requirements To Confirm

- `LINKEDIN_ACCESS_TOKEN`.
- `LINKEDIN_AUTHOR_URN`, for example `urn:li:organization:{id}` or member URN depending on target.
- Approved permissions for posting.
- Whether posts should be published immediately or saved for manual review only.

### API Flow

Based on LinkedIn docs:

1. Initialize image upload with Images API.
2. Upload the JPEG bytes to the returned upload URL.
3. Create a post through Posts API with `commentary`, `author`, `visibility`, `distribution`, `lifecycleState`, and image content.

### Success Criteria

- [ ] Publisher is behind an explicit CLI flag like `--publish`.
- [ ] Dry-run remains default.
- [ ] API errors do not mark local generation as failed.

---

## Testing Strategy

### Unit Tests

- LinkedIn commentary prompt includes required fields and constraints.
- Poster headline builder returns short readable headlines.
- Alt text builder includes repo name and metrics.
- Package builder returns complete `LinkedInPostPackage`.
- Renderer produces a path for the LinkedIn poster template.

### Integration Tests

- Existing Instagram caption/render tests continue to pass.
- New LinkedIn package generation can run from an `Evaluation` fixture without a DB migration.

### Manual Testing

1. Run the LinkedIn preview command.
2. Open the generated image.
3. Confirm the image is readable in a LinkedIn-like feed size.
4. Paste the commentary and attach the image manually to LinkedIn.
5. Check whether the first line, image headline, and final question create a coherent post.

## References

- Related research: `thoughts/shared/research/2026-05-08-evolving-ai-reporadar-content-strategy.md`
- Existing renderer: `src/render/renderer.py:82-138`
- Existing repo image template: `src/render/templates/repo_card.html:1-34`
- Existing image CSS: `src/render/static/style.css:8-124`
- Existing Instagram caption generator: `src/caption/generator.py:9-86`
- LinkedIn Posts API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-04
- LinkedIn Images API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api?view=li-lms-2026-04
- LinkedIn MultiImage API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/multiimage-post-api?view=li-lms-2026-04
