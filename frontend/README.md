# Frontend

This is the Vite + React frontend for PrivateIV / BolsaSim.

## Local Development

From the `frontend/` directory:

```bash
npm install
npm run dev
```

Required environment variable:

```env
VITE_API_URL=http://localhost:8000/api
```

For production, `VITE_API_URL` should point to the backend API root, for example:

```env
VITE_API_URL=https://your-backend-domain/api
```

## Build

```bash
npm run build
```

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
