# Local development

The hosted Railway services are intentionally paused. These instructions use your own local database and do not start any hosted service.

## Requirements

- Python 3.11
- Node.js 24.15 or newer in the 24.x line, and npm
- PostgreSQL only for a regular local setup; the fastest walkthrough below uses SQLite
- Redis only for background or scheduled jobs

## Fastest local walkthrough

This creates one fictional account and portfolio in a fresh temporary SQLite database. It needs no PostgreSQL, Redis, provider keys, or Railway services. From the repository root:

```bash
python3.11 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
SHOWCASE_DB_DIR=$(mktemp -d)
export DATABASE_URL="sqlite:///$SHOWCASE_DB_DIR/showcase.sqlite3"
export SECRET_KEY=local-showcase-only-key
export DEBUG=True
export SHOWCASE_PASSWORD=choose-a-local-only-password
backend/venv/bin/python backend/manage.py migrate
backend/venv/bin/python backend/manage.py create_showcase_portfolio --confirm-disposable
backend/venv/bin/python backend/manage.py runserver
```

In a second terminal, run `npm ci` and `npm run dev` from `frontend/`. Open `http://localhost:5173` and sign in as `showcase@example.invalid` with the password you chose. All trades, holdings, and prices are generated local data. Stop the servers and remove the temporary database directory when finished.

## Regular PostgreSQL development

From the repository root:

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set a development `SECRET_KEY`, `DEBUG=True`, and a local `DATABASE_URL` in `backend/.env`. Create the PostgreSQL database and role named by that URL before migrating; the sample `postgres:postgres` URL works only if that role, password, and `privateiv` database already exist. The [environment template](../backend/.env.example) has the remaining options. It is loaded only when `DJANGO_LOAD_DOTENV=true` is set:

```bash
export DJANGO_LOAD_DOTENV=true
python manage.py migrate
python manage.py runserver
```

The API is at `http://localhost:8000/api/`, and the database health check is at `http://localhost:8000/healthz/`.

## Start the client

In another terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. In development, the default `/api` URL is proxied to local Django; no frontend `.env` file is required. To target another API, set `VITE_API_URL` to its URL ending in `/api`. Never put API secrets in a `VITE_` variable.

## Explore generated data

Register a user on your **local** app, then run the guarded stress-data command only against a disposable development database:

```bash
cd backend
python manage.py create_test_portfolio --username you@example.com \
  --days 90 --transactions 60 --confirm-disposable
```

It requires `DEBUG=True`, writes stocks and historical prices, and refuses to replace an existing same-name portfolio unless `--reset` is explicit. No market-data provider key is required.

The guarded showcase command above refuses nonempty databases. The browser test automates its setup and removes its own temporary SQLite database afterward.

## Background jobs and providers

For scheduled prices, FX rates, benchmarks, and snapshots, set `BVL_API_KEY` and/or `FMP_API` as needed in `backend/.env`, provide local Redis via `CELERY_BROKER_URL`, and run these from `backend/` in separate terminals:

```bash
export DJANGO_LOAD_DOTENV=true
python manage.py sync_periodic_tasks
celery -A TradeSimulator worker --loglevel=info
```

```bash
export DJANGO_LOAD_DOTENV=true
celery -A TradeSimulator beat --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Schedules are versioned in [`periodic_tasks.json`](../backend/portfolio/config/periodic_tasks.json). Quotes come from configured providers, not a real-time market feed.

## Checks

From the repository root, with backend dependencies installed:

```bash
pytest
```

From `frontend/`:

```bash
npm run lint
npm test
npm run build
npm run test:e2e
```

The browser test uses a fresh temporary SQLite database. CI also migrates a disposable PostgreSQL database and runs `ops_smoke_test` with a stubbed benchmark provider. Neither check uses Railway.

From `frontend/`, after installing npm dependencies and Playwright Chromium, the browser test can use the backend virtual environment created above. `PYTHON_BIN` is resolved from the repository root by the test runner:

```bash
npx playwright install chromium
PYTHON_BIN=./backend/venv/bin/python npm run test:e2e
```

Pass `-- --capture-image` to that npm command to refresh [`authenticated-portfolio.png`](images/authenticated-portfolio.png). Review the image before committing it.

## API and deployment

Application endpoints are rooted at `/api/` and use cookie-backed sessions. Representative routes include `/api/auth/login/`, `/api/portfolios/`, `/api/transactions/create/`, and `/api/dashboard/`. For state-changing requests, obtain the CSRF cookie from `/api/csrf/` first.

The intended deployment is Vercel for `frontend/` and Railway for Django, PostgreSQL, Redis, worker, and beat. The [deployment runbook](../RAILWAY_DEPLOYMENT.md) documents reactivation prerequisites; [maintenance notes](maintenance.md) cover the dry-run legacy cost-basis audit. Do not turn on paid services just to run local checks.
