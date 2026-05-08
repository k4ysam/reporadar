# PRD: RepoRadar

A fully automated content pipeline that discovers trending GitHub repositories and standout hackathon projects, evaluates them for genuine signal, and publishes polished Instagram posts — zero human in the loop.

| | |
|---|---|
| **Status** | Draft v1.0 |
| **Date** | May 2026 |
| **Target launch** | v1 in ~3 weeks |
| **Automation** | 100% (post-setup) |

---

## Problem

Developers are on Instagram. Nobody is serving them well. Existing accounts covering GitHub or dev tools are either **human-curated newsletters** (slow, expensive, inconsistent) or **low-effort reposts** with no editorial judgment. There is no automated, opinionated, visual-first account surfacing what's actually worth paying attention to in the dev ecosystem this week.

---

## Goals

- **Full automation** — No human needed in the loop once the pipeline is live. Self-running on a schedule.
- **Editorial judgment** — LLM-powered signal filtering. Not just "most stars" — actual quality evaluation.
- **Instagram-native** — Posts designed for the platform. Carousels, strong hooks, visual code cards.
- **Defensible niche** — Dev innovation discovery account. Broad enough to grow, specific enough to own.

---

## Pipeline architecture

### 1. Discovery — dual source ingestion
Two parallel scrapers run on a cron. **GitHub:** Search API (primary, stable) + trending page scrape (secondary signal). Filter repos created in last 7 days with star velocity above threshold. **Hackathon:** Devpost scraper targeting projects submitted this week, filtered by prize-winning status and presence of a GitHub link. Devfolio as secondary source.

`GitHub Search API` `Playwright` `Devpost` `cron`

### 2. Deduplication & seen-log
Every candidate repo/project is checked against a persistent store (SQLite or simple JSON log). Skip anything posted in the last 30 days. Skip repos with fewer than a configurable star-velocity floor. This prevents repeat content and keeps the feed fresh.

`SQLite` `star velocity`

### 3. LLM evaluation
Each candidate is passed to Claude with a structured prompt. Evaluated on: README quality, novelty of the idea, real-world utility vs. demo toy, contributor health, and (for hackathon) ambition relative to time constraint. Output: a score (0–10), a one-sentence verdict, and a "skip" flag. Anything below threshold is dropped automatically.

`Claude API` `structured output` `scoring`

### 4. Sandbox trial (conditional)
For CLI tools and libraries only: spin up a Docker container, install the package, run basic usage, capture stdout. If install fails or requires auth/config → gracefully skip, mark as "code-reviewed only." For hackathon projects with a live demo URL → Playwright screenshot. This stage is best-effort, not blocking.

`Docker` `Playwright` `conditional`

### 5. Post generation
LLM generates caption (hook line, body, CTA, hashtags) using a template per content type. Visual: HTML-to-image via Puppeteer renders a code card or project summary card. Carousel slides for hackathon posts (hook → what it does → tech stack → team/link). Image is exported as JPEG ready for the Graph API.

`Puppeteer` `HTML-to-image` `carousel`

### 6. Instagram publish
Posts via the official Instagram Graph API using a Business account linked to a Facebook Page. Supports image posts and carousels. Posting times are varied within a ±15-minute window of target time to avoid pattern detection. Token refresh is automated. A post-publish log entry is written to the seen-store.

`Graph API` `long-lived token` `Business account`

---

## Content schedule

| Day | Type | Format |
|---|---|---|
| **Monday** | GitHub repo | Trending repo of the week — code card visual, single image post |
| **Wednesday** | Hackathon | Standout hackathon project — carousel format, "Built in X hours" hook |
| **Friday** | GitHub repo | Second repo of the week — code card visual, single image post |

---

## Success metrics (90 days)

| Metric | Target |
|---|---|
| Followers | 1k+ |
| Posts skipped by error | <5% |
| Avg engagement rate | 4%+ |
| API violations / flags | 0 |

---

## Competitive landscape

| Competitor | Description | Gap |
|---|---|---|
| TLDR / daily.dev | Human-curated dev content, newsletter-first. No Instagram presence. | No overlap |
| ByteByteGo | System design focused. Instagram presence but manually produced. | Adjacent |
| Devpost itself | Has social accounts but posts inconsistently, no editorial filter. | No overlap |
| GitHub trending bots | Twitter bots that just list repos. No evaluation, no Instagram, no visuals. | No overlap |

---

## Risks

| Severity | Risk | Mitigation |
|---|---|---|
| **High** | GitHub scrape breaking | Trending page layout change kills scraper. Search API as primary, scrape as bonus signal only. |
| **High** | Instagram token expiry | Long-lived tokens expire after 60 days. Automated refresh 2 weeks before expiry with alert on failure. |
| **Medium** | LLM misjudges hype | Model scores a bad repo highly. Confidence threshold + low-score skip; review log weekly early on. |
| **Medium** | Devpost scrape ToS | Gray area. Polite rate limits, respect robots.txt, attribute builders prominently in posts. |
| **Low** | Duplicate content | Same repo posted twice. Seen-log with 30-day TTL checked before every post generation step. |
| **Low** | Instagram pattern detection | Posting at exact same time daily flags automation. ±15 min random offset on all post times. |

---

## Pivots & expansions

- **Newsletter layer** — Same pipeline feeds a weekly Beehiiv digest. Email is algorithm-independent and buildable in parallel. Unlocks sponsorship revenue faster than Instagram.
- **Cross-platform publish** — Same generated content posted to X and LinkedIn with minor format tweaks. Minimal extra engineering, 3x distribution.
- **HackerNews "Show HN" source** — HN's Show HN feed is rich with indie builders. Same pipeline, new source. Adds a different demographic (solo hackers vs. hackathon teams).
- **B2B intel reports** — Sell the weekly trend-scouting output as a structured report to dev tool companies. Same data, different packaging. Subscription model, high margin.
- **Web destination** — Each post becomes a page on a website. SEO surface for "best hackathon projects 2026" type queries. Long-term moat that Instagram alone can't build.

---

## Build phases

### Phase 1 — Core loop (Week 1)
- GitHub Search API integration + dedup store
- LLM evaluator prompt + scoring
- Caption generator (repo template)
- Manual Instagram post (validate output quality)

### Phase 2 — Visuals + publish (Week 2)
- Puppeteer HTML-to-image code card renderer
- Instagram Graph API integration + token refresh
- GitHub trending scraper (secondary source)
- Full automated repo → post loop live

### Phase 3 — Hackathon source (Week 3)
- Devpost scraper + hackathon evaluator prompt
- Carousel post format + slide generator
- Content-type classifier routing
- Mixed schedule (Mon repo / Wed hackathon / Fri repo)

### Phase 4 — Sandbox trial (Week 4+)
- Docker sandbox for CLI tool execution
- Playwright demo screenshot for hackathon projects
- Graceful fallback if trial fails

---

## Out of scope (v1)

Automated engagement (likes, follows, comments). Reels format. Multi-platform publishing. Web destination. B2B reports. These are post-traction additions only.
