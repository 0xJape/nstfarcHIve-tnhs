# ARCHIVE Client Setup and Turnover Guide

## 1. System overview

ARCHIVE consists of:

- `archive-frontend/` — React, TypeScript, and Vite website.
- `arcHIVe-main/` — Python API, analytics runtime, models, and generated outputs.
- `region12-boundaries-export/` — Region XII geographic boundary data.
- `render.yaml` — Render Blueprint for API and PostgreSQL.

Production target: frontend on Vercel, backend and PostgreSQL on Render.

## 2. Required software

For local use on Windows, install:

- Git.
- Node.js 20 or newer with npm.
- Python 3.12 for API development, or Python 3.14 for full local analytics workflow.
- PostgreSQL only when testing mutable operational workflows locally.

## 3. Get project

Clone repository and enter it:

```powershell
git clone https://github.com/0xJape/nstfarcHIve-tnhs.git
Set-Location nstfarcHIve-tnhs
```

## 4. Configure backend

Create virtual environment and install API dependencies:

```powershell
py -3.12 -m venv .venv-1
.\.venv-1\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\arcHIVe-main\requirements-api.txt
```

Copy `arcHIVe-main/.env.example` to `arcHIVe-main/.env`, then replace placeholders. Never commit `.env`.

Required for operational/admin workflows:

- `DATABASE_URL`
- `ARCHIVE_ADMIN_USERNAME`
- `ARCHIVE_ADMIN_PASSWORD`

Recommended production settings:

- `ARCHIVE_CORS_ORIGIN` — exact Vercel origin.
- `ARCHIVE_PUBLIC_URL` — exact Vercel origin.
- `MAKE_WEBHOOK_URL` — only when Make integration is enabled.
- `GROQ_API_KEY` — only when AI features are enabled.

Use long, unique admin credentials. Share them through password manager, never email or repository.

## 5. Configure frontend

```powershell
Set-Location .\archive-frontend
Copy-Item .env.example .env.local
npm install
```

For local use, keep:

```text
VITE_API_BASE_URL=http://127.0.0.1:8765
```

`VITE_` values are public browser configuration. Never place secrets there.

## 6. Run locally

From repository root, after backend and frontend setup:

```powershell
.\START_ALL.bat
```

Open:

- Website: `http://127.0.0.1:5173`
- API health: `http://127.0.0.1:8765/api/health`

If `START_ALL.bat` is unsuitable, run services separately:

```powershell
Set-Location .\arcHIVe-main
..\.venv-1\Scripts\python.exe -m src.phase2_runtime_api --host 127.0.0.1 --port 8765 --cors-origin http://127.0.0.1:5173
```

```powershell
Set-Location .\archive-frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 7. Production deployment

### Render

1. Create Render Blueprint from repository `main` branch.
2. Use repository-root `render.yaml`.
3. Let Blueprint create `archive-api` and `archive-operational-db`.
4. Enter all variables marked `sync: false` in Render dashboard.
5. Confirm `https://<render-service>/api/health` returns HTTP 200.

### Vercel

1. Import same GitHub repository.
2. Set Root Directory to `archive-frontend`.
3. Set `VITE_API_BASE_URL=https://<render-service>.onrender.com`.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Deploy, then set Render `ARCHIVE_CORS_ORIGIN` and `ARCHIVE_PUBLIC_URL` to exact Vercel production origin.
7. Redeploy Render after changing those values.

## 8. Turnover validation

Before acceptance, verify:

1. `npm run lint` succeeds.
2. `npm run build` succeeds.
3. API starts without traceback.
4. `/api/health` returns HTTP 200.
5. Map and analytics load from API.
6. Education and support pages work on desktop and mobile.
7. Admin login uses client-owned credentials.
8. Browser console contains no failed API or CORS requests.
9. Render and Vercel projects belong to client-owned accounts.
10. Client has GitHub repository access and billing ownership.

## 9. Client ownership checklist

Transfer or document ownership for:

- GitHub repository and branch protections.
- Render service, PostgreSQL database, environment variables, and billing.
- Vercel project, domains, environment variables, and billing.
- Make workflow and webhook, if enabled.
- Groq/API accounts, if enabled.
- Domain registrar and DNS records, if custom domain is used.
- Password-manager records for admin and service credentials.

Do not transfer local `.env` files, local SQLite authentication databases, virtual environments, or `node_modules`.

## 10. Backup and rollback

- Keep PostgreSQL backups according to client retention policy.
- Preserve latest known-good Render and Vercel deployments.
- Roll back by redeploying previous revisions, then verify `/api/health`, one map request, and one analytics request.
- Generated analytics SQLite outputs are reproducible and not replacement for PostgreSQL backups.

## 11. Known operating constraints

- Render free services may sleep and have slow first request.
- Render filesystem is ephemeral.
- Analytics SQLite files are read-only generated outputs.
- PostgreSQL is required for durable accounts, admin edits, facilities, inquiries, audit logs, announcements, and saved data.
- Published health information and generated regional data require owner review before release.

## 12. Support references

- Repository overview: `README.md`
- Deployment details: `DEPLOYMENT.md`
- Backend operation: `arcHIVe-main/README.md`
- API contract: `API_CONTRACT.md`