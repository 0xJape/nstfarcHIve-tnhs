# arcHIVe

Region XII HIV awareness, care-referral, and spatiotemporal analytics platform.

## Repository structure

- `archive-frontend/` — React, TypeScript, and Vite frontend; deploy to Vercel.
- `arcHIVe-main/` — Python API and analytics runtime; deploy to Render.
- `region12-boundaries-export/` — Region XII GeoJSON boundary data.
- `render.yaml` — Render Blueprint for API and PostgreSQL.

## Production deployment

### Render API

1. In Render, create a Blueprint from this repository's `main` branch.
2. Use root Blueprint path `render.yaml`.
3. Enter required environment values directly in Render; never commit secrets.
4. Blueprint creates `archive-api` and `archive-operational-db`.
5. Verify `https://<render-service>/api/health` returns HTTP 200.

Required secret or deployment-specific variables are documented in `arcHIVe-main/.env.example`.

### Vercel frontend

1. Import this repository into Vercel.
2. Set Root Directory to `archive-frontend`.
3. Set `VITE_API_BASE_URL` to Render API HTTPS origin.
4. Build with `npm run build`; output directory is `dist`.
5. Update Render variables `ARCHIVE_CORS_ORIGIN` and `ARCHIVE_PUBLIC_URL` to exact Vercel production origin.

## Local documentation

- Backend setup and API endpoints: `arcHIVe-main/README.md`
- Frontend source: `archive-frontend/`

Keep `.env` files local. Commit only sanitized `.env.example` templates.
