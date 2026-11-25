# College Management System — Security Audit & Production Configuration

## 1. Security Audit Findings & Implemented Fixes

| Severity | Finding | Resolution Implemented |
| :--- | :--- | :--- |
| **High** | No rate limiting on `POST /api/v1/auth/login` | Added sliding-window `InMemoryRateLimiter` (`app/core/rate_limit.py`) keyed by `(client_ip, email)`, returning `429 Too Many Requests` + `Retry-After` without permanently locking accounts. |
| **High** | Missing production config validation | Updated `Settings` (`app/core/config.py`) to reject `DEBUG=true`, weak/placeholder `SECRET_KEY` (`<32` chars), and wildcard `*` CORS origins when `ENVIRONMENT=production`. |
| **Medium** | Admin CLI accepted `--password` flag | Removed `--password` CLI flag from `app/cli/create_admin.py`; now uses `ADMIN_INITIAL_PASSWORD` env var or interactive `getpass.getpass()`. |
| **Medium** | No centralized logging or global 500 handler | Added `app/core/logging_config.py` and global `Exception` handler in `app/main.py` returning generic `500` without stack traces. |
| **Medium** | Overly permissive CORS methods/headers & exposed docs in prod | Restricted `CORSMiddleware` to explicit methods/headers; disabled `/docs`, `/redoc`, and `/openapi.json` when `ENVIRONMENT=production` and `DEBUG=false`. |
| **Medium** | Default SQLAlchemy pool settings | Configured `pool_size`, `max_overflow`, `pool_recycle`, and `pool_pre_ping=True` via environment variables. |
| **Low** | `jwt.decode` did not require `sub`/`exp`/`iat` | Enforced `options={"require": ["sub", "exp", "iat"]}` in `decode_access_token`. |
| **Low** | `SubmissionCreate.file_url` allowed arbitrary schemes | Restricted `file_url` to `http://` and `https://` in `app/schemas/assignment.py`. |

---

## 2. Environment Variables

| Variable | Description | Dev Default |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development`, `staging`, or `production` (`APP_ENV` alias supported) | `development` |
| `DEBUG` | Enable debug mode (must be `false` in production) | `true` (`.env`) / `false` (default) |
| `LOG_LEVEL` | Python logging level (`INFO`, `WARNING`, etc.) | `INFO` |
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+psycopg://...`) | Required |
| `DB_POOL_SIZE` | SQLAlchemy connection pool size | `10` |
| `DB_MAX_OVERFLOW` | SQLAlchemy max overflow connections | `20` |
| `DB_POOL_RECYCLE` | Connection recycle interval (seconds) | `1800` |
| `SECRET_KEY` | JWT signing key (must be >= 32 random chars in production) | Required |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime in minutes | `30` |
| `FRONTEND_URL` | Comma-separated explicit allowed CORS origins | `http://127.0.0.1:5500` |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | Max login attempts per window | `5` |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window in seconds | `60` |

---

## 3. Authentication & Frontend Storage Decisions

- **Stateless Short-Lived JWTs + DB Lookup:** Every protected request verifies the `HS256` signature, expiration, and required claims, then loads the user from PostgreSQL (`get_current_user` + `require_active_user`) so deactivated accounts are blocked immediately.
- **Rate Limiting Across Multiple Instances:** The current `InMemoryRateLimiter` protects single-instance deployments. For multi-worker or horizontally scaled production deployments, swap in a **Redis-backed sliding-window limiter** (e.g., using `redis.asyncio` / `INCR` + `EXPIRE` or Lua script) behind the same `check_and_record(key)` interface.
- **Frontend `sessionStorage` Evaluation:** The Vanilla JS frontend stores the JWT in `sessionStorage` rather than `localStorage` so tokens do not persist across browser restarts, and escapes all dynamic values with `escapeHtml()`. For higher-security production deployments, migrating to **SameSite=Lax/Strict `HttpOnly` Secure cookies** (set by `/auth/login` and cleared by `/auth/logout`, with CSRF double-submit or `Origin` checks) is recommended to eliminate JS token readability.

---

## 4. Running in Production

```bash
export ENVIRONMENT=production
export DEBUG=false
export SECRET_KEY="<64-char-cryptographically-random-secret>"
export DATABASE_URL="postgresql+psycopg://<user>:<password>@<db-host>:5432/<db-name>"
export FRONTEND_URL="https://portal.example.edu"

cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
