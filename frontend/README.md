# IntelliMandate — React Frontend

React + Vite + Tailwind v4 rebuild of the IntelliMandate Streamlit frontend, for Canara Bank's
regulatory compliance dashboard.

## Setup

```bash
npm install
```

Set your backend URL in `.env` (copy from `.env.example`):

```bash
cp .env.example .env
# edit .env: VITE_BACKEND_URL=http://localhost:8000
```

## Run dev server

```bash
npm run dev
```

Opens at http://localhost:5173

## Build for production

```bash
npm run build
```

Output goes to `dist/`. Serve with any static host, or:

```bash
npm run preview
```

## Pages

- `/` — Dashboard (MAP priority list, metrics, exposure chart)
- `/mandates` — Mandate history, scrape controls, live polling
- `/map/:mapId` — MAP detail, MPI gauge, Wing assignments, regulatory impact
- `/upload-circular` — Manual circular upload with live orchestrator reasoning log
- `/evidence` — Evidence upload with live 4-gate validation
- `/audit-trail` — Compliance certificates, expandable detail per closed MAP

## Notes

- All API calls live in `src/lib/api.js` — single source of truth for backend endpoints.
- Design tokens (colors, fonts) live in `src/index.css` as CSS variables — same dark theme
  as the original Streamlit app (Syne / Instrument Sans / JetBrains Mono).
- Backend response shape is defensively unwrapped in `api.js` (`{maps: [...]}` vs plain
  array, etc.) since the FastAPI backend wraps list responses in an object.
