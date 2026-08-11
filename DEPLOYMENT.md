# ARCHIVE Deployment

## Target

- Frontend: Vercel.
- Backend: Render web service.
- Initial backend storage: generated SQLite and static output files.
- Future mutable storage: PostgreSQL.

## Render Backend

Root directory: `arcHIVe-main`

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
python -m src.phase2_runtime_api --host 0.0.0.0 --port $PORT --cors-origin $ARCHIVE_CORS_ORIGIN
```

Required environment variables:

- `ARCHIVE_CORS_ORIGIN`: exact Vercel frontend origin.
- `ARCHIVE_RUN_DIR`: optional absolute or deploy-relative completed run directory.

The service needs a completed Phase 2 run before API startup. Generate outputs during build/deploy, commit a known read-only output only when appropriate, or use external object storage later.

## Vercel Frontend

Set:

```text
VITE_API_BASE_URL=https://<render-service>.onrender.com
```

Frontend calls API routes using `${VITE_API_BASE_URL}/api/...`.

Do not place secrets in Vite variables. Values beginning with `VITE_` are browser-visible.

## CORS

Production CORS must use exact frontend origin:

```text
https://<vercel-project>.vercel.app
```

Do not use `*` in production.

## Health Check

Render health-check path:

```text
/api/health
```

Expected status: `200` when service and latest completed run are available.

## Deployment Smoke Test

1. Render service starts without traceback.
2. `GET /api/health` returns `200`.
3. `GET /api/dates` returns available `YYYY-MM` values.
4. `GET /api/geometry/municipalities` returns GeoJSON.
5. `GET /api/snapshot?period=<available-period>` returns aggregate rows.
6. Vercel frontend loads.
7. Frontend displays map and one analytics view.
8. Browser console has no failed API or CORS requests.

## Runtime Constraints

Render filesystem is ephemeral. Do not treat runtime SQLite changes as durable production storage.

Safe initial use:

- Read-only generated analytics.
- Static model artifacts.
- Static boundary files.
- Generated reports that can be recreated.

Future PostgreSQL/object storage required for:

- User accounts.
- Admin-managed facilities.
- Support inquiries.
- Announcements.
- Audit logs.
- Consent records.
- Saved user data.
- Durable report history.

## Security Checklist

- Bind Render service to `0.0.0.0`.
- Use Render `$PORT`.
- Set exact CORS origin.
- Keep secrets in Render/Vercel environment settings.
- Do not expose database paths in public responses.
- Do not return internal exception details in production.
- Add authentication before exposing admin or mutable endpoints.
- Review generated data before publication.

## Rollback

1. Redeploy previous known-good Render revision.
2. Restore previous Vercel deployment.
3. Confirm `/api/health`.
4. Confirm one snapshot and geometry request.
5. Record failure and affected run ID.
