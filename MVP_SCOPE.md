# ARCHIVE MVP Scope

## Purpose

Define first release boundary for ARCHIVE. MVP connects public HIV information with backend-generated Region XII analytics for authorized health officials.

## MVP Users

### Public visitor

- Browse approved HIV education content.
- View prevention and testing information.
- Search approved testing centers and treatment facilities.
- View contact and location details.
- Submit general support inquiry without creating an account.

### Health official

- Sign in through protected account.
- View analytics dashboard.
- View GIS risk map.
- Inspect forecast scenarios.
- Review hotspot analysis.
- Open municipality profiles.
- Review generated alerts.
- Export CSV and generated reports.

### System administrator

- Manage official user accounts and roles.
- Manage facility directory records.
- Review audit events.
- Configure approved thresholds and content.

## Included MVP Features

1. Public home page.
2. HIV education pages.
3. Testing-center and treatment-facility locator.
4. Health-official login.
5. Role-based administrator access.
6. Analytics dashboard.
7. GIS risk map.
8. Forecast scenario view.
9. Hotspot analysis view.
10. Municipality profile view.
11. Alert center.
12. CSV export and generated report access.
13. Backend health and run-status checks.
14. Privacy notice and medical-disclaimer content.

## Backend Dependencies

The MVP consumes `arcHIVe-main` outputs and API services:

- Historical municipality-level data.
- Forecast values.
- Spatial and hotspot results.
- Decomposition results.
- Alerts.
- Testing-center recommendations.
- Municipality boundaries.
- Generated maps, charts, reports, CSV, GeoJSON, and SQLite data.

## Explicitly Out of MVP

- LLM health assistant.
- Anonymous AI risk assessment.
- Public user accounts.
- Automated SMS/email notifications.
- Individual-level case records.
- Facility capacity tracking.
- Age and sex analytics unless verified source data is added.
- Medical diagnosis or clinical triage.
- Automated intervention execution.
- Full executive reporting suite.
- Online appointment booking.
- Community discussion features.

## MVP Acceptance Criteria

- Public pages work without login.
- Protected analytics pages reject unauthenticated users.
- Public views expose aggregate data only.
- Dashboard clearly labels historical data and forecast scenarios.
- Map supports Region XII municipality inspection.
- Forecast and hotspot views identify period and model run.
- Empty, stale, failed, and unavailable data states are visible.
- CSV export matches displayed filters.
- Administrator actions produce audit events.
- Keyboard navigation and visible focus states work.
- No AI output claims to diagnose HIV.
- Backend verification passes before release.

## Release Gates

### Gate 1: Data

- Required backend run completes.
- Boundary data validates.
- 49 expected model locations are present.
- Forecast periods are normalized to `YYYY-MM`.

### Gate 2: Security

- Authentication works.
- Roles are enforced server-side.
- Secrets stay outside source control.
- CORS permits approved origins only.
- Public endpoints exclude sensitive records.

### Gate 3: Usability

- Core public and official flows work on desktop and mobile.
- Loading, empty, error, and stale states exist.
- Public health wording is reviewed.

### Gate 4: Release

- API tests pass.
- Accessibility checks pass.
- Browser smoke flows pass.
- Backup and rollback steps are documented.
