# Deployment runbook

BolsaSim's public frontend is hosted on Vercel at [bolsasim.com](https://bolsasim.com/). The Railway API, PostgreSQL, Redis, worker, and beat services are intentionally paused. The public `/preview` page uses fictional data and does not need Railway. Do not start services simply to view the portfolio project.

## Architecture when the interactive demo is enabled

| Service | Host | Purpose |
| --- | --- | --- |
| React/Vite frontend | Vercel (`frontend/`) | Static site and authenticated client |
| Django API | Railway (`backend/`) | REST API and migrations |
| PostgreSQL | Railway | Accounts, trades, prices, and Celery results |
| Redis | Railway | Celery message broker |
| Celery worker | Railway (`backend/`) | Background jobs |
| Celery beat | Railway (`backend/`) | Scheduled ingestion and snapshots |

The web process is configured in [`backend/nixpacks.toml`](backend/nixpacks.toml). Worker and beat commands are in [`backend/Procfile`](backend/Procfile). Beat is only optional when scheduled work is deliberately disabled; otherwise run exactly one beat instance.

## Before intentionally reactivating Railway

1. Back up the database. Audit any older cost basis with `python manage.py repair_trade_basis --portfolio-id <id>` on a database copy first. Review stock currencies and recorded FX rates before considering `--apply`; the command never edits production data automatically.
2. Configure the API, worker, and beat with the same Django signing key and database connection. Point `CELERY_BROKER_URL` at Redis. Celery results use `django-db` in [`backend/TradeSimulator/settings.py`](backend/TradeSimulator/settings.py); do **not** set a Redis `CELERY_RESULT_BACKEND` variable.
3. Set `ALLOWED_HOSTS` to the actual API hostname and set `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and `FRONTEND_URL` for `https://bolsasim.com`. Store `SECRET_KEY`, `DATABASE_URL`, `FMP_API`, and any `BVL_API_KEY` in Railway variables, never in Git. See [`backend/.env.example`](backend/.env.example) for variable names. Replace service names in reference variables with the names in your Railway project, for example `DATABASE_URL=${{Postgres.DATABASE_URL}}` and `CELERY_BROKER_URL=${{Redis.REDIS_URL}}`.
4. Start the API, worker, and one beat instance only when you intend to run the interactive system. Check migrations, `/healthz/`, worker readiness, and schedules. The `ops_smoke_test` command exercises auth, trading, and snapshots using disposable data; run it only against an environment where those writes are intended. Use `--benchmark-mode stub` to avoid a live provider call.
5. Build the Vercel frontend from `frontend/` with `VITE_API_URL=https://<your-api-host>/api`. Keep the default paused preview until the backend is healthy. Only then set `VITE_DEMO_PAUSED=false` and redeploy Vercel to expose registration and trading.

Railway variables are staged until deployed; review pending changes before applying them. For current platform UI and reference-variable behavior, consult [Railway's variable documentation](https://docs.railway.com/variables). Vercel's [Vite guide](https://vercel.com/docs/frameworks/frontend/vite) covers frontend build settings.
