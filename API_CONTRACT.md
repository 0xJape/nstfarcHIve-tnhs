# ARCHIVE API Contract

## Base URL

Local: `http://127.0.0.1:8765`

Production: Render service URL, supplied to frontend through `VITE_API_BASE_URL`.

All JSON responses use UTF-8. Period values use `YYYY-MM`.

## Common Rules

- `GET` endpoints are read-only.
- Query parameters are URL-encoded.
- Lists return JSON arrays.
- Errors return `{ "error": "..." }`.
- Successful runs expose aggregate municipality-level analytics.
- Public clients must not receive individual health records.
- Frontend must show historical values and forecast scenarios separately.

## Endpoints

| Method | Route | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/health` | Service and run status | Public |
| `GET` | `/api/version` | API version | Public |
| `GET` | `/api/metadata` | Run metadata | Public/aggregate |
| `GET` | `/api/dates` | Available forecast periods | Public |
| `GET` | `/api/municipalities` | Municipality metadata | Public/aggregate |
| `GET` | `/api/snapshot?period=YYYY-MM` | Municipality values for period | Public/aggregate |
| `GET` | `/api/ranking?period=YYYY-MM&metric=...&limit=49` | Ranked municipalities | Public/aggregate |
| `GET` | `/api/timeline?location=NAME` | Municipality timeline | Public/aggregate |
| `GET` | `/api/timeline?psgc=CODE` | Municipality timeline by PSGC | Public/aggregate |
| `GET` | `/api/hotspots?period=YYYY-MM` | Hotspot results | Public/aggregate |
| `GET` | `/api/transmission?period=YYYY-MM` | Transmission pressure | Public/aggregate |
| `GET` | `/api/compartments?period=YYYY-MM&location=NAME` | Compartment dynamics | Public/aggregate |
| `GET` | `/api/decomposition?location=NAME` | Trend/seasonal decomposition | Public/aggregate |
| `GET` | `/api/testing-centers` | Testing-center recommendations | Public/aggregate |
| `GET` | `/api/alerts?limit=500` | Generated alerts | Public/aggregate |
| `GET` | `/api/region-summary` | Regional summary | Public/aggregate |
| `GET` | `/api/adjacency` | Municipality adjacency | Public/aggregate |
| `GET` | `/api/geometry/municipalities` | Municipality GeoJSON | Public |
| `GET` | `/api/geometry/provinces` | Province GeoJSON | Public |
| `GET` | `/api/geometry/region` | Region GeoJSON | Public |
| `GET` | `/map` | Generated Leaflet map | Public |

## Ranking Metrics

Allowed `metric` values:

- `PREDICTED_CASES`
- `NEW_INFECTIONS_ESTIMATE`
- `ROLLING_12M_RATE_PER_100K`
- `GI_STAR_Z_SCORE`
- `TRANSMISSION_PRESSURE_INDEX`
- `TESTING_CENTER_NEED_SCORE`
- `EFFECTIVE_INFECTIOUS_POOL`
- `TESTING_ACCESS_SCORE`
- `VIRAL_SUPPRESSION_COVERAGE`

Unknown metrics return HTTP `400`.

## Example Response Shapes

### Health

```json
{
  "status": "ok",
  "api_version": "2.2.1-verification-fix",
  "run_dir": "...",
  "database": "..."
}
```

Production responses should avoid exposing local filesystem paths.

### Forecast row

Fields depend on generated database schema. Frontend must use returned field names and treat numeric values as numbers. Important fields include:

- `PERIOD`
- `PSGC`
- `PROVINCE`
- `LOCATION`
- `PREDICTED_CASES`
- `TRANSMISSION_PRESSURE_INDEX`
- `HOTSPOT_CLASS`
- `TESTING_CENTER_NEED_SCORE`

### Error

```json
{
  "error": "Provide location"
}
```

HTTP statuses:

- `200` success.
- `204` successful CORS preflight.
- `400` invalid query.
- `404` unknown route or missing file.
- `500` server failure.

## Frontend Rules

- Fetch `/api/dates` once, then use selected period for snapshot, ranking, hotspots, and transmission calls.
- Load geometry once and cache it in memory.
- Show loading, empty, stale, and error states.
- Do not assume every optional field exists.
- Do not present forecast values as confirmed case counts.
- Do not expose database paths, exception details, or internal run files.

## Future Compatibility

Current API serves generated read-only analytics. Future PostgreSQL-backed features should preserve these route meanings where possible. User accounts, facility edits, inquiries, announcements, audit logs, and consent records need separate authenticated endpoints.
