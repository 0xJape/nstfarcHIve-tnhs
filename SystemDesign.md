# ARCHIVE System Design

## Purpose

ARCHIVE is a public HIV education and healthcare-navigation platform with an administrator Control Center for Region XII aggregate surveillance, GIS analysis, forecasting, hotspot detection, and intervention planning.

## User Model

ARCHIVE uses two roles:

- `user`: public visitor or registered user. People living with HIV are included as users; HIV status never determines permissions.
- `administrator`: authorized health-system operator.

Public access does not require an account for education, facility search, or aggregate map viewing.

## MVP Boundary

The MVP uses aggregate municipality-level surveillance data. It does not store or manage individual patient records.

Forecast values are scenarios, not confirmed diagnoses or guaranteed outcomes. Public features provide education and healthcare navigation, not medical diagnosis.

`arcHIVe-main` is the backend analytics layer. It provides forecasting, GIS processing, spatial statistics, alerts, recommendations, generated outputs, SQLite storage, and read-only API routes.

## Public Website

Public users can:

### Home

- Learn ARCHIVE purpose.
- View approved aggregate awareness information.
- Open education, map, and facility-locator actions.

### Risk Map

- View Region XII municipalities.
- View aggregate risk indicators.
- View hotspot status.
- View increasing, stable, or decreasing trend where available.
- View approved public advisories.
- Find nearby facilities.

Public map must not expose individual records or unsafe small-count data.

### HIV Education

- HIV basics.
- HIV and AIDS distinction.
- Transmission and prevention.
- PrEP and PEP information.
- Myths and facts.
- Testing process.
- ART and living with HIV.
- Approved downloadable resources.

### Facility Locator

Shows approved records for available:

- Testing centers.
- Treatment hubs.
- RHUs.
- Hospitals.
- Laboratories.
- Community clinics.
- NGOs and support organizations.

Facility details may include address, contact, services, hours, and directions when verified.

### Optional Future Public Features

- Anonymous risk assessment.
- Safety-constrained health assistant.
- Contact health officer.
- Community support portal.
- News and announcements.
- Optional user account.

These features require approved content, safety review, consent rules, and supporting services before release.

## Administrator Control Center

Administrators can access public features plus protected aggregate analytics.

### Overview

- Latest valid run status.
- Historical aggregate values.
- Forecast scenario summary.
- Active hotspot count.
- High-priority municipalities.
- Testing-center recommendations.
- Generated alerts.
- Model version and limitations.

Do not call this value `AI Confidence` unless uncertainty and evaluation methodology are defined. Prefer `Forecast Uncertainty` or `Model Metrics`.

### Risk Map

Admin layers may include:

- Aggregate historical values.
- Forecast scenarios.
- Risk indicators.
- Hotspots.
- Testing-center recommendations.
- Municipality boundaries.
- Spatial statistics.

### Surveillance Data Management

MVP supports:

- Import validated aggregate CSV.
- Validate schema, locations, periods, and values.
- Review validation errors.
- Track import/run status.
- Preserve the last valid run when a new run fails.

Individual patient case management is future scope. Do not build `Add`, `Edit`, or `Delete HIV Case` until PostgreSQL, encryption, authorization, audit, retention, consent, and backup requirements exist.

### Forecasting

- MLR-LSTM forecast scenarios.
- Forecast charts.
- Historical-versus-forecast labels.
- Model version.
- Data period.
- Uncertainty or evaluation metrics where available.

### Hotspot Analysis

- Current hotspot classification.
- Emerging and persistent hotspot views where available.
- Hotspot rankings.
- Moran's I.
- Getis-Ord Gi*.
- Clear method and limitation descriptions.

### Municipality Profiles

Show available aggregate fields:

- Population.
- Historical values.
- Trend.
- Forecast scenario.
- Hotspot status.
- Testing-center need.
- Recommended intervention.
- Model explanation or contributing indicators where available.

### Alerts

- New hotspot alerts.
- Forecast increase alerts.
- High-priority municipality alerts.
- Testing-center need alerts.
- Model-generated reason and period.
- Review status when alert workflow exists.

### Reports

MVP supports available CSV and generated report outputs. PDF, Excel, monthly, quarterly, and annual formats are future requirements unless implemented and tested.

### Administration

Future authenticated services:

- Manage official users.
- Manage facility records.
- Review audit logs.
- Configure alert thresholds.
- Manage approved content.
- Configure notification preferences.

## Navigation

### Public

```text
ARCHIVE
├── Home
├── Risk Map
├── Education
├── Find Care
├── About
└── Optional Future Features
    ├── AI Assistant
    ├── Risk Assessment
    ├── News
    └── Contact
```

### Administrator

```text
ARCHIVE
├── Public Navigation
└── Control Center
    ├── Overview
    ├── Risk Map
    ├── Surveillance Data
    ├── Forecasting
    ├── Hotspot Analysis
    ├── Municipality Profiles
    ├── Alerts
    ├── Reports
    ├── Facilities
    ├── Users
    ├── Audit Logs
    └── Settings
```

## Data Visibility

| Data | Public user | Administrator |
|---|---:|---:|
| HIV education | Read | Read/manage when authorized |
| Facility directory | Read approved | Read/write when authorized |
| Aggregate municipality indicators | Read approved | Read |
| Forecast scenarios | Limited approved view | Read |
| Spatial statistics | Limited summary | Read |
| Individual patient records | Deny | Deny in MVP |
| User accounts | Own account only | Manage authorized accounts |
| Audit logs | Deny | Read authorized logs |

## Safety and Privacy

- Do not diagnose HIV.
- Do not infer HIV status from account or behavior.
- Do not store anonymous risk answers without explicit consent.
- Use aggregate public data and suppress unsafe small counts.
- Apply server-side authorization to protected routes.
- Audit administrative changes and exports.
- Use approved health sources for public content.
- Show data period, model version, and limitations.
- Refer urgent or clinical questions to qualified healthcare services.

## Deployment Boundary

- Frontend deploys to Vercel.
- Backend deploys to Render.
- Initial analytics remain generated read-only SQLite/files.
- Future PostgreSQL stores accounts, facility edits, inquiries, announcements, audit logs, consent records, and other mutable data.
- Runtime Render filesystem is not durable storage.
