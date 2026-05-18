# Deploying RepoRadar on Render

This deploys the entire pipeline as **one Render web service** that runs both:

- The Flask dashboard (`src.operator_api.web.app`)
- The APScheduler daily pipeline (in-process via `BackgroundScheduler`)

A 1 GB Persistent Disk is mounted at `/var/data/output` for rendered post images so the dashboard can serve what the scheduler wrote. Supabase Postgres stays as the database.

## Cost

- Web Service **Starter** plan: $7/mo
- Persistent Disk 1 GB: ~$0.25/mo
- Total: **~$7.25/mo** (plus Supabase, OpenAI, GitHub PAT — all unchanged)

## One-time setup

### 1. Prep the repo

The committed `render.yaml`, `.python-version`, updated `requirements.txt`, and `src/operator_api/web/wsgi.py` are the only things Render needs. Commit and push them to the branch you want to deploy from (the blueprint defaults to `main`).

### 2. Create the service from the blueprint

1. Sign in at [render.com](https://render.com) and connect your GitHub account.
2. Click **New → Blueprint**.
3. Select the `reporadar` repo.
4. Render reads `render.yaml` and shows you the planned service. Confirm.

Render then prompts you for every env var that has `sync: false` (secrets). Paste in:

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Supabase project → Settings → Database → **Transaction pooler** URL (port 6543). URL-encode special chars in the password — `@` → `%40`. |
| `GH_TOKEN` | github.com/settings/tokens → new fine-grained PAT, no scopes needed for public repos |
| `OPENAI_API_KEY` | platform.openai.com → API keys. Required even on `LLM_PROVIDER=claude/gemini` (image gen always uses OpenAI). |
| `ANTHROPIC_API_KEY` | Only if `LLM_PROVIDER=claude` |
| `GEMINI_API_KEY` | Only if `LLM_PROVIDER=gemini` |
| LinkedIn / Instagram / image-host keys | Optional — only needed if you'll click "Publish now" in the dashboard. Leave blank to run in manual-export mode. |

Non-secret values (`LLM_PROVIDER`, `SCHEDULE_HOUR`, thresholds, etc.) are already set in `render.yaml`. You can edit them later in the Render UI without touching code.

### 3. Deploy

Render will:

1. Provision the disk at `/var/data/output`.
2. Run `pip install -r requirements.txt`.
3. Run `python migrations/apply.py` (pre-deploy hook) — idempotent, applies the v2 schema if missing.
4. Boot `gunicorn -w 1 -k gthread --threads 8 --timeout 180 -b 0.0.0.0:$PORT src.operator_api.web.wsgi:app`.

The dashboard becomes reachable at `https://reporadar-<hash>.onrender.com/`.

You can rename the service or wire up a custom domain from the Render dashboard.

## Verifying the deploy

After the first deploy is green:

1. Open the dashboard URL. The dashboard should render (initially empty).
2. From **Render Shell** (Service → Shell tab) run `python -m src verify-env`. This pings GitHub, the LLM provider, the output disk, and Postgres. All four should report OK.
3. Trigger a one-shot run from the dashboard: click **Run pipeline** (`POST /api/run`). Takes 1–3 minutes (LLM + image API calls). When it finishes, refresh the dashboard — the new post appears under "Recent posts" with a thumbnail served from the persistent disk.

## How the scheduler runs in production

The daily pipeline is scheduled by `APScheduler.BackgroundScheduler`, started at gunicorn boot inside `src/operator_api/web/wsgi.py`. It fires once per day at `SCHEDULE_HOUR` ± `SCHEDULE_JITTER_MINUTES` in the configured `TIMEZONE`.

**Why a single gunicorn worker (`-w 1`)**: BackgroundScheduler lives in the worker process. Running multiple workers would fire the cron job once per worker. If you ever need more throughput on the dashboard, scale via additional Render **instances** (separate machines, each with its own scheduler — and then you'd need to gate the cron to one instance, e.g. with an APScheduler Postgres jobstore. Not needed at MVP scale).

If the service is suspended by Render (free plan only), the scheduler stops firing. Starter plan and above stay running 24/7.

## Updating env vars

Edit them in the Render UI (Service → Environment → Edit). Render restarts the service automatically. The pre-deploy migration runs again on each restart but is idempotent.

## Updating the code

`autoDeploy: true` in `render.yaml` means every push to the configured branch (`main`) triggers a redeploy. Disable from the UI if you'd rather promote deploys manually.

## Common gotchas

- **`prepared statement "_pg3_N" does not exist`** — your `DATABASE_URL` is pointing at the **session pooler** (port 5432). The transaction pooler (port 6543) is what `src/common/db.py` is configured for.
- **`prepared statement` errors after a deploy of new code** — same root cause, transient if the pooler hasn't yet recycled backends; resolves on the next request.
- **No images appear after a `Run pipeline` button click** — confirm the disk is mounted at `/var/data/output` and `OUTPUT_DIR=/var/data/output`. `ls /var/data/output` from the Render Shell should show the JPEGs.
- **Scheduler never fires** — confirm one of: (a) you're on Starter plan or higher (free plan suspends on idle), (b) `SCHEDULE_HOUR` is in `TIMEZONE` you expect, (c) check Render logs for the "In-process scheduler started" line at boot.

## Reverting to separate processes

If you later want to split the dashboard and scheduler into separate Render services (e.g. to scale the web independently), you'll need to move image storage off the local disk first — Render disks can only attach to one service. The publishing service already has `src/publishing/image_host.py` for Instagram; reusing that path for **all** rendered images is the natural seam.
