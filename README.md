# RepoRadar

Scans GitHub for repositories with anomalous star velocity, scores them with Gemini, and surfaces a daily digest via a local web dashboard.

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create your `.env` file**
```bash
cp .env.template .env
```

Fill in two values:

| Key | Where to get it |
|-----|----------------|
| `GH_TOKEN` | GitHub → Settings → Developer Settings → Personal access tokens → **no scopes needed** (zero checkboxes) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |

## Daily workflow

```bash
python -m src scan      # find fast-rising repos (~10 GitHub API calls)
python -m src evaluate  # score with Gemini (~5 calls, fits free tier)
python -m src serve     # open dashboard at http://localhost:8000
```

## Dashboard

`python -m src serve` starts a local Flask server. The dashboard shows:
- **Today's scans** — repos found and their star growth
- **Evaluations** — Gemini scores (novelty, explainability, overall) with summaries
- **Recent runs** — pipeline history and status

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CANDIDATES_PER_RUN` | 15 | Max repos surfaced per scan |
| `MAX_EVALUATIONS_PER_RUN` | 5 | Max Gemini calls per evaluate run |
| `STAR_GROWTH_MIN_PCT` | 200 | Minimum % star growth to qualify |
| `STAR_BASE_MIN` | 20 | Minimum star count to qualify |
| `VELOCITY_WINDOW_HOURS` | 48 | Lookback window for growth calculation |
| `LLM_MODEL` | gemini-2.0-flash | Gemini model name |
| `DB_PATH` | reporadar.db | SQLite database path |

## API usage

Gemini free tier: 15 requests/minute, 1,500/day. A single `evaluate` run uses at most `MAX_EVALUATIONS_PER_RUN` calls (default 5).

GitHub unauthenticated rate limit is 60 requests/hour. With a PAT (any tier, no scopes needed) it is 5,000/hour.

## Tests

```bash
python -m pytest tests/ -q
```
