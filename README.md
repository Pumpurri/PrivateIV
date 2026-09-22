# PrivateIV

PrivateIV is a full-stack investment simulator for building and tracking virtual portfolios across the Peruvian and U.S. markets. The user-facing application is branded as **BolsaSim** and is designed for educational use: it combines simulated trading, PEN/USD cash management, live market data, historical valuations, and portfolio performance analytics in one responsive dashboard.

> PrivateIV is an educational simulator. It does not execute real trades or provide investment advice.

> **Demo status:** The hosted Railway backend and background workers are intentionally paused. The frontend can be previewed, but sign-in, trading, and live market data will not work until the backend is redeployed.

![BolsaSim landing page captured from a local frontend run](docs/images/landing.png)

## Features

- Email-based registration and session authentication
- Multiple portfolios with configurable base and reporting currencies
- Simulated buys, sells, deposits, withdrawals, and PEN/USD conversions
- Separate PEN and USD cash balances with transaction-time FX rates
- Current positions, cost basis, unrealized and realized profit/loss
- Historical portfolio snapshots and time-weighted return (TWR)
- Performance comparisons against configurable market benchmarks
- Market data for Bolsa de Valores de Lima (BVL) and U.S. securities
- PEN/USD exchange-rate ingestion from Banco Central de Reserva del Perú (BCRP)
- Scheduled price, FX, snapshot, and performance updates with Celery
- Responsive React dashboard with Vercel Analytics and Speed Insights support

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 6, React Router, Axios |
| Backend | Django 5, Django REST Framework |
| Database | PostgreSQL |
| Background jobs | Celery, Redis, django-celery-beat |
| Market data | BVL Data on Demand, Financial Modeling Prep, BCRP |
| Deployment | Vercel (frontend), Railway/Nixpacks (backend) |
| Observability | Datadog APM (optional) |

## Architecture

```text
React/Vite client
       |
       | session-authenticated REST requests
       v
Django REST API --------------------> PostgreSQL
       |
       | queues scheduled and background work
       v
Redis <---- Celery worker / beat ----> BVL, FMP, and BCRP APIs
```

The backend is split into three Django apps:

- `users` handles registration, login, logout, password reset, and profiles.
- `stocks` stores security data and refreshes local and U.S. prices.
- `portfolio` handles portfolios, transactions, holdings, FX, benchmarks, snapshots, and performance calculations.

## Getting started

### Prerequisites

- Python 3.11
- Node.js 18 or newer and npm
- PostgreSQL
- Redis, if you want to run background or scheduled jobs

### 1. Clone the repository

```bash
git clone https://github.com/Pumpurri/PrivateIV.git
cd PrivateIV
```

### 2. Configure the backend

Create and activate a virtual environment, then install the Python dependencies:

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy the example environment file:

```bash
cp .env.example .env
```

For a minimal local setup, update these values in `backend/.env`:

```env
SECRET_KEY=replace-with-a-random-development-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://localhost:8000
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/privateiv
CELERY_BROKER_URL=redis://localhost:6379/0
```

The project only loads `backend/.env` when explicitly enabled. Export the opt-in flag, prepare the database, and start Django:

```bash
export DJANGO_LOAD_DOTENV=true
python manage.py migrate
python manage.py sync_periodic_tasks
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`; its health endpoint is `http://localhost:8000/healthz/`.

### 3. Configure the frontend

In a second terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000/api
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:5173` in your browser.

## Market data and background jobs

The application can run without scheduled jobs for basic development, but current quotes, FX rates, benchmarks, and daily snapshots depend on the configured providers and Celery services.

Add provider credentials to `backend/.env` when needed:

```env
BVL_API_KEY=your-bvl-data-on-demand-key
FMP_API=your-financial-modeling-prep-key
```

With Redis running, start the worker and scheduler from `backend/` in separate terminals:

```bash
export DJANGO_LOAD_DOTENV=true
celery -A TradeSimulator worker --loglevel=info
```

```bash
export DJANGO_LOAD_DOTENV=true
celery -A TradeSimulator beat --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Scheduled jobs are versioned in `backend/portfolio/config/periodic_tasks.json`. Run `python manage.py sync_periodic_tasks` after changing that manifest.

## Useful commands

Run backend tests from the repository root:

```bash
pytest
```

Check and build the frontend:

```bash
cd frontend
npm run lint
npm run build
```

Create an administrator account:

```bash
cd backend
export DJANGO_LOAD_DOTENV=true
python manage.py createsuperuser
```

Populate a small starter set of U.S. stocks:

```bash
python manage.py populate_stocks
```

## Environment variables

The complete backend template is in [`backend/.env.example`](backend/.env.example). The most important settings are:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Required Django signing key |
| `DEBUG` | Enables local Django debug mode |
| `DATABASE_URL` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | Redis connection string for Celery |
| `ALLOWED_HOSTS` | Hosts accepted by Django |
| `CORS_ALLOWED_ORIGINS` | Frontend origins allowed to call the API |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for authenticated write requests |
| `FRONTEND_URL` | Base URL used in frontend-facing links |
| `BVL_API_KEY` | Optional BVL market-data credential |
| `FMP_API` | Financial Modeling Prep credential |
| `VITE_API_URL` | Frontend API base URL; include the `/api` suffix |

Keep secrets in local or hosting-platform environment variables. Do not commit `.env` files or credentials.

## Deployment

The repository includes deployment configuration for the intended split architecture:

- Deploy `frontend/` to Vercel. Use `npm run build`, publish `dist/`, and set `VITE_API_URL` to the public backend URL ending in `/api`.
- Deploy `backend/` to Railway with PostgreSQL and Redis services. Run separate web, Celery worker, and Celery beat processes with the same backend environment variables.
- Add the deployed frontend origin to both `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`.

See [`RAILWAY_DEPLOYMENT.md`](RAILWAY_DEPLOYMENT.md) for the service-by-service Railway setup and [`backend/OBSERVABILITY.md`](backend/OBSERVABILITY.md) for operational checks and Datadog configuration.

## API overview

All application endpoints are rooted at `/api/` and use cookie-backed session authentication.

| Area | Representative endpoints |
| --- | --- |
| Authentication | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/logout/`, `/api/auth/me/` |
| Portfolios | `/api/portfolios/`, `/api/portfolios/<id>/holdings/`, `/api/portfolios/<id>/performance/` |
| Transactions | `/api/transactions/`, `/api/transactions/create/` |
| Dashboard | `/api/dashboard/`, `/api/dashboard/portfolios/<id>/overview/` |
| Stocks and FX | `/api/stocks/`, `/api/stocks/last-refresh/`, `/api/fx-rates/` |

For authenticated state-changing requests, first obtain the CSRF cookie from `/api/csrf/` and send credentials with subsequent requests.
