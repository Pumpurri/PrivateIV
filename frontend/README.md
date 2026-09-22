# Frontend

This is the Vite + React frontend for PrivateIV / BolsaSim.

Use Node.js 24.15 or newer in the 24.x line; the installed browser-test dependencies do not support Node 18.

## Local Development

From the `frontend/` directory:

```bash
npm ci
npm run dev
```

The default `/api` URL is proxied to local Django at `http://localhost:8000`; no frontend `.env` file is required for local development. To target another backend, set:

```env
VITE_API_URL=http://localhost:8000/api
```

For production, `VITE_API_URL` should point to the backend API root, for example:

```env
VITE_API_URL=https://your-backend-domain/api
```

Production builds default to a read-only preview while the hosted backend is paused. In this mode, `/login` and `/register` show a pause notice rather than collecting credentials. The public `/preview` route uses fictional data and makes no API request. When the backend is available again, set `VITE_DEMO_PAUSED=false` for the production build and redeploy.

See the [local development guide](../docs/development.md) for backend setup and the disposable authenticated browser test.

## Build

```bash
npm run build
```

Run lint and frontend tests with `npm run lint` and `npm test`. With backend Python dependencies and Playwright Chromium installed, `npm run test:e2e` exercises login, balances, and a paper trade against a temporary local database.

## Static Assets

- Favicon: `public/SB-favicon.png`
- Vite serves files in `public/` from the site root

## Vercel

Recommended project settings:

- Root Directory: `frontend`
- Build Command: `npm run build`
- Output Directory: `dist`
- Install Command: `npm install`

## Vercel Analytics

Web Analytics is already wired into the app with `@vercel/analytics` in `src/App.jsx`.

To use it in production:

1. Enable Web Analytics in the Vercel project dashboard
2. Deploy the frontend
3. Visit the deployed site to start collecting page views

## Vercel Speed Insights

Speed Insights is already wired into the app with `@vercel/speed-insights` in `src/App.jsx`.

To use it in production:

1. Enable Speed Insights in the Vercel project dashboard
2. Deploy the frontend
3. Visit the deployed site to start collecting Core Web Vitals data
