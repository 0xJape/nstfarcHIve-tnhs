# Render-to-Vercel Deployment

ARCHIVE uses separate frontend and backend deployments:

- **Render:** Python API
- **Vercel:** Vite/React frontend

## 1. Render Backend

Render hosts the API from `arcHIVe-main`.

Recommended settings:

- Root directory: `arcHIVe-main`
- Runtime: Python
- Build command: `pip install -r requirements-api.txt`
- Start command: `python -m src.phase2_runtime_api --host 0.0.0.0 --port $PORT`
- Health-check path: `/api/health`

Required environment variables:

```text
ARCHIVE_CORS_ORIGIN=https://<vercel-project>.vercel.app
ARCHIVE_PUBLIC_URL=https://<render-service>.onrender.com
```

Render must have completed Phase 2 output data available before API startup. The API serves read-only analytics, generated model output, SQLite data, and municipality boundary files.

## 2. Vercel Frontend

Vercel hosts `archive-frontend`.

Set this production environment variable in Vercel:

```text
VITE_API_BASE_URL=https://<render-service>.onrender.com
```

`VITE_` variables are browser-visible. Do not store secrets in them.

During the Vite build, this value becomes the frontend API base URL. `src/api.ts` uses it for every request:

```ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765'
```

## 3. Frontend-to-Backend Data Flow

`App.tsx` loads initial data from Render:

```ts
Promise.all([
  api.health(),
  api.dates(),
  api.geometry(),
  api.historicalTrend(),
])
```

The frontend then loads the latest snapshot and ranking data. The map renders only after geometry and rows exist:

```tsx
geometry && rows.length
  ? <MapView geometry={geometry} rows={rows} metric={metric} />
  : <div>Map data unavailable</div>
```

## 4. Why Map Loads Correctly on Vercel

`MapView.tsx` uses `react-leaflet` and receives GeoJSON from Render:

```ts
import 'leaflet/dist/leaflet.css'
```

The municipality boundaries render through Leaflet's `GeoJSON` component. `FitRegion` then:

1. Converts GeoJSON into Leaflet bounds.
2. Checks that bounds are valid.
3. Calls `map.fitBounds(...)` to center and zoom on Region XII.
4. Uses `ResizeObserver` and `map.invalidateSize()` so the map redraws after layout changes.

This prevents common blank-map and incorrect-size problems caused by rendering Leaflet inside a page that changes size after mount.

Map tiles load directly from CARTO:

```tsx
<TileLayer
  attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
  url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
  subdomains="abcd"
/>
```

## 5. CORS

Render must allow the exact Vercel origin:

```text
ARCHIVE_CORS_ORIGIN=https://<vercel-project>.vercel.app
```

Do not use `*` in production.

The browser flow is:

```text
Vercel frontend
    -> https://<render-service>.onrender.com/api/geometry/municipalities
    -> Render API returns GeoJSON
    -> React stores geometry in state
    -> MapView renders Leaflet GeoJSON
```

## 6. Loading State

`App.tsx` starts with `dataLoading = true` and displays a loading card while Render requests complete:

```tsx
{dataLoading && <div className="data-loading" role="status">
  Loading regional data
</div>}
```

If an API request fails, the loader stops and the UI shows its fallback message instead of attempting to render an incomplete map.

## 7. Deployment Smoke Test

Run these checks in order:

1. Render service starts without traceback.
2. `GET https://<render-service>.onrender.com/api/health` returns `200`.
3. `GET /api/dates` returns available `YYYY-MM` periods.
4. `GET /api/geometry/municipalities` returns a GeoJSON `FeatureCollection`.
5. `GET /api/snapshot?period=<available-period>` returns rows.
6. Vercel frontend loads.
7. Browser network panel shows successful API and tile requests.
8. Map displays municipality boundaries and data overlays.
9. Browser console shows no CORS errors.

## 8. Important Deployment Detail

Keep Render and frontend configuration consistent. Current repository files use:

- `DEPLOYMENT.md` for deployment documentation.
- `render.yaml` for Render Blueprint configuration.
- `archive-frontend/.env.example` for local frontend API configuration.

If Render uses a different requirements file or start command, update both deployment settings and documentation together.

## 9. Storage Constraint

Render filesystem storage is ephemeral. Current deployment is safe for:

- Read-only generated analytics.
- Static model artifacts.
- Static boundary files.
- Re-creatable reports.

PostgreSQL or object storage is required later for durable accounts, admin edits, facilities, inquiries, audit logs, consent records, saved data, and report history.
