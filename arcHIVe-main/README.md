
## Scope

- Region: SOCCSKSARGEN (Region XII)
- Map level: 49 municipalities and cities
- Forecast period: January 2025 to December 2050
- Simulation: monthly population growth, HIV care cascade, treatment effects, neighboring transmission pressure, and testing-center expansion
- Spatial analysis: Getis–Ord Gi*, global and local Moran statistics, and connected hotspot clusters
- Main output: full-screen Leaflet map, charts, tables, GeoJSON, CSV, SQLite, and HTML report

## Windows requirements

Install standard 64-bit Python 3.14.5 or later within the Python 3.14 series. The launcher creates its environment at `%LOCALAPPDATA%\arcHIVe\py314` to avoid Windows path-length installation errors.

## Run the system

1. Extract the complete folder to a short path such as `C:\arcHIVe`.
2. Keep internet access enabled on the first run so actual Region XII municipality boundaries can be downloaded and validated.
3. Double-click `VERIFY_PACKAGE.bat`. It installs the dependencies, completes an offline model, simulation, map, database, and API test, then closes the temporary database before removing verification outputs.
4. Double-click `RUN_SYSTEM.bat`.
5. The newest report and Leaflet map open automatically after a successful run.

Generated runs are saved under `outputs/phase2_run_YYYYMMDD_HHMMSS`.

## Start the API

Run the simulation at least once, then double-click `START_API.bat`.

Default address: `http://127.0.0.1:8765`

Patient, appointment, facility, audit, and notification records use PostgreSQL through `DATABASE_URL`. Analytics remain in generated read-only SQLite. Set `DATABASE_URL` before enabling operational workflows; API startup initializes required tables. Render blueprint provisions PostgreSQL automatically.

Common endpoints:

- `GET /api/health`
- `GET /api/version`
- `GET /api/metadata`
- `GET /api/dates`
- `GET /api/municipalities`
- `GET /api/snapshot?period=2030-12`
- `GET /api/ranking?period=2030-12&metric=TRANSMISSION_PRESSURE_INDEX`
- `GET /api/timeline?location=KORONADAL`
- `GET /api/hotspots?period=2030-12`
- `GET /api/transmission?period=2030-12`
- `GET /api/compartments?location=KORONADAL`
- `GET /api/decomposition?location=KORONADAL`
- `GET /api/testing-centers`
- `GET /api/alerts`
- `GET /api/region-summary`
- `GET /api/adjacency`
- `GET /api/geometry/municipalities`
- `GET /api/geometry/provinces`
- `GET /api/geometry/region`
- `GET /map`

The API reads the SQLite database in the latest successful run. The next frontend should load the geometry once, then request snapshots, rankings, alerts, transmission values, testing-center recommendations, and timelines when the selected month changes.

## Configuration

`spatiotemporal_config.json` controls the forecast period, regional growth damping, population growth, migration, HIV care-cascade flows, treatment effects, neighboring transmission pressure, spatial diffusion, uncertainty, testing-center establishment, alert thresholds, boundary validation, playback speed, and output settings.

`.env.example` lists the optional API environment variables. Copy it to `.env` only when the selected runtime or frontend tooling loads environment files.

## Important folders

- `src`: simulation, spatial analysis, map generation, output generation, and API code
- `scripts`: package verification
- `data`: municipal model input data
- `models`: trained MLR–LSTM artifacts
- `outputs`: generated at runtime

