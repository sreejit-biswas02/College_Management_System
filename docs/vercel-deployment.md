# Vercel Single-Project Deployment Guide

This repository is configured to deploy both the **static frontend** (`frontend/`) and the **FastAPI backend** (`backend/app/`) as a **single Vercel project**.

## Architecture on Vercel

- `vercel.json`:
  - Runs `cd frontend && VERCEL=1 sh build.sh` to build `frontend/dist` with `API_BASE_URL="/api/v1"` (same-origin) and cache-busted asset URLs.
  - Rewrites `/api/*` and `/health*` to `/api/index.py`.
  - Rewrites client-side routes to `/index.html`.
- `api/index.py`: Adds `backend/` to `sys.path` and exposes `app` from `backend/app/main.py`.
- `requirements.txt` & `.python-version`: Declares Python `3.12` and runtime dependencies at the repository root for Vercel's Python runtime.
- `backend/app/database/connection.py`: Automatically switches to SQLAlchemy `NullPool` when `VERCEL=1` so serverless invocations do not hold stale pooled connections (pair with Neon's `-pooler` URL).

## Vercel Project Settings

- **Framework Preset:** `Other`
- **Root Directory:** `.` (repository root)
- **Build Command:** Managed by `vercel.json` (`cd frontend && VERCEL=1 sh build.sh`)
- **Output Directory:** Managed by `vercel.json` (`frontend/dist`)

## Required Environment Variables (Vercel Project Settings)

Set all variables in **Vercel → Project → Settings → Environment Variables** (never commit secrets to Git):

| Variable | Example / Notes |
|---|---|
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `LOG_LEVEL` | `INFO` |
| `SECRET_KEY` | Random secret >= 32 characters (e.g. `openssl rand -hex 32`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `FRONTEND_URL` | `https://your-project.vercel.app` (required by production validator) |
| `DATABASE_URL` | Neon **pooled** URL with `?sslmode=require` |
| `DIRECT_DATABASE_URL` | Neon **direct** (unpooled) URL with `?sslmode=require` (for Alembic) |
| `STORAGE_PROVIDER` | `r2` |
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key ID |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret access key |
| `R2_BUCKET_NAME` | Private R2 bucket name |
| `R2_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `STORAGE_TIMEOUT_SECONDS` | `15` |
| `SIGNED_URL_EXPIRE_SECONDS` | `300` |

## Database Migrations (Controlled Step)

Do **not** run Alembic inside serverless request handlers. Run migrations from your local machine or CI/CD against `DIRECT_DATABASE_URL` before promoting a deployment:

```bash
cd backend
DIRECT_DATABASE_URL="postgresql+psycopg://..." uv run alembic upgrade head
```

To bootstrap the initial administrator account:

```bash
cd backend
DATABASE_URL="postgresql+psycopg://..." uv run python -m app.cli.create_admin \
  --email admin@college.edu \
  --full-name "System Admin"
```

## Serverless Limitations to Note

1. **Upload Payload Limit (4.5 MB):** Vercel serverless functions enforce a 4.5 MB request body limit. Uploads proxied through `/api/v1/assignments/*/attachments` or `/api/v1/submissions/*/files` larger than 4.5 MB will receive `413` from Vercel unless direct-to-R2 presigned PUT uploads are added later. Signed downloads go directly to R2 and are unaffected.
2. **In-Memory Login Rate Limiter:** `backend/app/core/rate_limit.py` stores login attempts in process memory. Across multiple Vercel serverless instances, rate-limit counters are per-instance rather than globally shared.
3. **CORS & Preview URLs:** If you test Vercel preview deployments (`https://<branch>-<project>.vercel.app`), add those preview origins to `FRONTEND_URL` (comma-separated) if cross-origin requests are made, or use same-origin `/api/v1`.
