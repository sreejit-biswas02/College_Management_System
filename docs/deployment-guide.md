# College Management System — Cloud Deployment Guide

## 1. Architecture Overview

| Component | Platform | Role |
| :--- | :--- | :--- |
| **Frontend** | Cloudflare Pages | Static HTML5, CSS3, Vanilla JS ES modules (`frontend/`) |
| **Backend** | Render Web Service | FastAPI + Uvicorn + `uv` (`backend/`) |
| **Database** | Neon PostgreSQL | Managed PostgreSQL 16 (pooled + direct URLs) |
| **Object Storage** | Cloudflare R2 | Private S3-compatible bucket for file uploads |
| **Source Control** | GitHub | Monorepo root |

---

## 2. Production Environment Variables (Render)

| Variable | Description |
| :--- | :--- |
| `ENVIRONMENT` | Set to `production` |
| `DEBUG` | Set to `false` (enforced at startup) |
| `LOG_LEVEL` | `INFO` |
| `SECRET_KEY` | Strong random secret (`>= 32` chars; e.g. `openssl rand -hex 32`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `DATABASE_URL` | Neon **pooled** connection string with `?sslmode=require` |
| `DIRECT_DATABASE_URL` | Neon **direct** connection string with `?sslmode=require` (used by Alembic) |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE` | `10` / `20` / `1800` |
| `FRONTEND_URL` | Exact Cloudflare Pages origin (`https://<project>.pages.dev`) |
| `STORAGE_PROVIDER` | `r2` |
| `R2_ACCOUNT_ID` | Cloudflare Account ID |
| `R2_ACCESS_KEY_ID` | R2 Object Read & Write Access Key ID |
| `R2_SECRET_ACCESS_KEY` | R2 Secret Access Key |
| `R2_BUCKET_NAME` | Private R2 bucket name |
| `R2_ENDPOINT_URL` | `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` |

---

## 3. Step-by-Step Deployment Checklist

1. **GitHub Repository:** Push the monorepo to a private or public GitHub repository (verify `.env` and `frontend/dist/` are not tracked).
2. **Neon PostgreSQL Project:** Create a Neon project, copy both the **Pooled** connection string (`DATABASE_URL`) and **Direct** connection string (`DIRECT_DATABASE_URL`), ensuring `?sslmode=require` is present.
3. **Cloudflare R2 Bucket:** Create a private bucket (e.g., `college-management-files`) with public access **disabled**.
4. **Cloudflare R2 API Token:** Create an R2 API token with **Object Read & Write** permission scoped to your bucket.
5. **Render Web Service:** Connect your GitHub repo using [render.yaml](file:///home/sreejit-biswas/Documents/College-Management-System/render.yaml) (root directory `backend`, build `uv sync --frozen`, start `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/health`).
6. **Render Environment Variables:** Set all secret variables listed in Section 2 (temporarily set `FRONTEND_URL` to your planned `https://<project>.pages.dev` URL, then update if needed).
7. **Cloudflare Pages:** Connect the same GitHub repo with:
   - **Root directory:** `frontend`
   - **Build command:** `sh build.sh`
   - **Build output directory:** `dist`
8. **Cloudflare Pages Environment Variable:** Set `API_BASE_URL=https://<your-render-service>.onrender.com/api/v1` (build-time only; never put backend secrets here).
9. **Run Alembic Migrations:** Using `DIRECT_DATABASE_URL` from a secure shell / Render Shell:
   ```bash
   cd backend && uv run alembic upgrade head
   ```
10. **Bootstrap First Admin Account:**
    ```bash
    cd backend && uv run python -m app.cli.create_admin --email admin@college.edu --full-name "System Admin"
    ```
    *(Enter password interactively when prompted.)*
11. **Verify API Health:** Check `GET https://<render-url>/health` and `GET https://<render-url>/health/database`.
12. **Verify Frontend Connectivity:** Open `https://<project>.pages.dev`, confirm login works and no CORS/mixed-content errors appear in DevTools.
13. **Test File Uploads & Downloads:** Upload a PDF assignment attachment as Faculty and download it as an enrolled Student.
14. **Verify Role Workflows:** Exercise Admin, Faculty, and Student dashboards end-to-end.

---

## 4. Hosting Limitations & Scaling Notes

- **Render Free Tier Cold Starts:** Render free web services spin down after inactivity, causing a 30–50s cold start on the first request.
- **Rate Limiting Across Multiple Workers:** The built-in `InMemoryRateLimiter` works for a single Render instance/worker. If scaling to multiple workers or instances, switch to a Redis-backed rate limiter.
- **Custom Domains:** When adding custom domains (`https://portal.college.edu`, `https://api.college.edu`), update `FRONTEND_URL` on Render and `API_BASE_URL` on Cloudflare Pages, then redeploy.
