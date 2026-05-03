# PRD: RepoRadar
### Automated GitHub Discovery Newsletter — Instagram + Web

**Author:** Samaksh  
**Status:** Draft  
**Last Updated:** May 2, 2026

---

## Problem

There are thousands of genuinely interesting GitHub repos that never break through. GitHub Trending captures what's already popular. newsletters like TLDR cover repos after they've already blown up. The signal — a repo spiking fast before anyone has heard of it — exists in the data but nobody has built an automated editorial layer on top of it.

Manual "Day 1 of cool repos" accounts exist but they're inconsistent, burn out, and rely entirely on one person's bandwidth and taste.

---

## Solution

An automated pipeline that monitors GitHub for repos with anomalous star velocity, uses Claude to evaluate and write about the most interesting ones, surfaces a human-review digest daily, and auto-publishes approved picks to Instagram (and optionally a web feed).

The human stays in the loop for taste. The machine does the discovery and writing.

---

## Users

**Primary:** The operator (you). This is an internal tool that runs a public content product.  
**Secondary:** Instagram followers who discover repos through the posts.

---

## Goals

- Find 2–3 genuinely interesting, under-the-radar repos per day
- Maintain posting consistency without manual effort
- Build a content moat around star velocity as an editorial signal
- Portfolio-worthy pipeline: GitHub API + Claude + Instagram Graph API + scheduler

---

## Non-Goals

- Building a public-facing web app in v1
- Fully autonomous posting with no human review
- Covering repos that are already mainstream

---

## Pipeline Architecture

```
GitHub API (star velocity scan)
        ↓
Filter & Score (Python)
        ↓
Claude evaluation (README + commits + issues)
        ↓
Daily digest → Human review (you approve/reject)
        ↓
Auto-format → Instagram Graph API → Scheduled post
```

---

## Feature Breakdown

### 1. Star Velocity Scanner

**What it does:** Hits the GitHub API daily to find repos with anomalous star growth over the last 24–48hrs.

**Signal:** Not total stars — rate of growth. A repo going 50 → 500 stars in 48hrs is the target. One sitting at 50k is not.

**Filters:**
- Exclude repos already on GitHub Trending
- Exclude repos covered by TLDR, HN front page, or similar in the last 7 days (optional v2)
- Minimum threshold: e.g. >200% star growth in 48hrs with a base of at least 20 stars
- Language filter: configurable (default: all)

**Output:** Ranked list of 10–15 repo candidates with raw star delta and growth rate.

**API used:** `GET /repos/{owner}/{repo}` + `GET /repos/{owner}/{repo}/stargazers` with timestamps, or GitHub Archive / GH Torrent for historical data.

---

### 2. AI Evaluation Agent

**What it does:** For each candidate repo, Claude reads:
- README
- Recent commits (last 10)
- Open issues (top 10 by engagement)
- Repo description + topics

**Output per repo:**
```json
{
  "repo": "owner/repo-name",
  "stars_48h": 450,
  "growth_pct": 312,
  "summary": "One paragraph plain-English explanation of what it does",
  "why_interesting": "Why this is worth paying attention to right now",
  "audience": "Who this is for — developers, designers, researchers, etc.",
  "novelty_score": 8,
  "explainability_score": 9,
  "overall_score": 8.5
}
```

**Scoring rubric:**
- **Novelty** (1–10): Is this genuinely new or a clone of something existing?
- **Explainability** (1–10): Can this be explained in one Instagram caption to a general dev audience?
- **Overall** (1–10): Weighted composite, used to rank the shortlist

**Output:** Top 3–5 repos with full evaluations, ranked by overall score.

---

### 3. Human Review Digest

**What it does:** Sends you a daily digest (email or Telegram message) with the top picks. For each:
- Repo name + link
- Star velocity stats
- Claude's summary + why interesting
- Two buttons: ✅ Approve / ❌ Reject

**Implementation options:**
- Simple: Python script outputs a formatted markdown file you open manually
- Better: Telegram bot — each pick is a message with inline approve/reject buttons
- Best v2: Minimal web dashboard at localhost

**Approved repos** get passed to the formatter. Rejected ones are logged and excluded from future consideration for 30 days.

---

### 4. Post Formatter

**What it does:** Takes an approved repo and generates the Instagram post assets.

**Caption format:**
```
🔭 [Repo Name] by @owner

[One-line hook — what it does]

[2–3 bullets on why it's interesting]

⭐ [X stars in 48hrs]
🔗 Link in bio

#github #opensource #programming #buildinpublic [relevant tags]
```

**Image:** Auto-generated card with:
- Repo name in large type
- Star velocity stat
- Short tagline
- Minimal dark background, code aesthetic

**Image generation options:**
- Python + Pillow for v1 (simple, fully local)
- HTML template → headless Chrome screenshot for v2 (more polish)

---

### 5. Instagram Publisher

**What it does:** Schedules and posts the formatted content to Instagram.

**API:** Instagram Graph API (requires Facebook Developer account + connected Instagram Business account)

**Flow:**
1. Upload image to Instagram container endpoint
2. Attach caption
3. Schedule publish time (optimal: 9am or 7pm based on engagement data)
4. Confirm post

**Rate limits:** Instagram allows ~25 posts/day — well within scope.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| Scheduler | `cron` or `APScheduler` |
| GitHub data | GitHub REST API (free, 5000 req/hr authenticated) |
| AI evaluation | Claude API (claude-sonnet-4) |
| Digest delivery | Telegram Bot API |
| Image generation | Pillow (v1) |
| Publishing | Instagram Graph API |
| Storage | SQLite (repo history, approval log, post log) |

---

## Data Model

**repos_seen**
```
id, owner, name, first_seen_at, stars_at_detection, stars_48h_delta, growth_pct, excluded_until
```

**evaluations**
```
id, repo_id, evaluated_at, summary, why_interesting, novelty_score, explainability_score, overall_score, approved (bool)
```

**posts**
```
id, repo_id, evaluation_id, caption, image_path, posted_at, instagram_post_id
```

---

## Build Order

1. **GitHub star velocity scanner** — get the data pipeline working, validate the signal is real
2. **Claude evaluation** — prompt engineering to get consistent, good writeups
3. **Telegram digest** — approve/reject loop
4. **Image card generator** — Pillow template
5. **Instagram Graph API** — connect and test posting
6. **End-to-end test** — full run, one real post
7. **Cron automation** — set it and forget it

Estimated time: 2–3 focused weekends.

---

## Risks

| Risk | Mitigation |
|---|---|
| GitHub API rate limits | Authenticated requests = 5000/hr, more than enough |
| Instagram Graph API is painful to set up | Budget a day just for this — it requires business account, Facebook app approval |
| Claude writes boring summaries | Invest in prompt engineering early, lock it in before automating |
| Star velocity signal is noisy (spam repos, follow-for-follow bots) | Add secondary filters: repo age, commit activity, contributor count |
| Burn out on approving daily | Keep approval lightweight — Telegram inline buttons, <2 min/day |

---

## Success Metrics

- Pipeline runs daily without intervention
- 5+ posts per week published
- Approval rate >50% (signal quality is good)
- At least one repo discovered that blows up after posting (the dream)

---

## Future / V2

- Web dashboard instead of Telegram for review
- Cross-post to Twitter/X and a web newsletter
- Public "leaderboard" of repos discovered vs their eventual star count
- Let followers submit repo nominations
- Kalshi-style prediction: "will this repo hit 1k stars in 7 days?"