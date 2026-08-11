# ARCHIVE MVP Requirements

Requirements derived from `SystemDesign.md` and constrained by `MVP_SCOPE.md`.

## Public Experience

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `PUB-001` | Visitor can open ARCHIVE home page without authentication. | Must | Frontend | Home page loads and presents purpose, prevention links, and clear navigation. | Ready |
| `PUB-002` | Visitor can browse approved HIV education content. | Must | Content service | Education categories open without login and display reviewed content. | Ready |
| `PUB-003` | Visitor can search approved testing and treatment facilities. | Must | Facility dataset, map service | Search returns matching facilities with name, location, contact, and services. | Ready |
| `PUB-004` | Visitor can view facility details on a map. | Must | Boundary and facility data | Selecting facility shows map location and available details. | Ready |
| `PUB-005` | Visitor can submit a general support inquiry without public account. | Should | Support endpoint | Valid inquiry submits; invalid input returns field-level errors. | Proposed |
| `PUB-006` | Public content states ARCHIVE does not diagnose HIV or replace clinical care. | Must | Approved content | Disclaimer appears on risk, assistant, and health guidance surfaces. | Ready |

## Health Official Experience

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `OFF-001` | Health official can authenticate before accessing protected analytics. | Must | Authentication, role service | Unauthenticated analytics request is denied; authorized request succeeds. | Proposed |
| `OFF-002` | Health official can view latest valid analytics run summary. | Must | Backend API, run metadata | Dashboard shows run date, data period, model version, and status. | Proposed |
| `OFF-003` | Health official can view aggregate municipality risk data. | Must | Forecast and spatial outputs | Dashboard shows municipality, period, risk indicators, and scenario labels. | Ready |
| `OFF-004` | Health official can inspect Region XII GIS risk map. | Must | GeoJSON, map service | Map displays municipality boundaries and selectable risk information. | Ready |
| `OFF-005` | Health official can inspect forecast scenarios by municipality and period. | Must | Forecast API | Selection returns forecast value, period, location, and scenario label. | Ready |
| `OFF-006` | Health official can inspect hotspot classifications and rankings. | Must | Hotspot outputs | View distinguishes emerging, persistent, declining, and other classifications where available. | Ready |
| `OFF-007` | Health official can open a municipality profile. | Must | Municipality, forecast, hotspot APIs | Profile shows available population, trend, forecast, hotspot, and intervention fields. | Ready |
| `OFF-008` | Health official can review generated alerts. | Must | Alert outputs | Alert view shows period, location, severity, reason, and status. | Ready |
| `OFF-009` | Health official can export filtered aggregate results. | Must | CSV/report outputs | Export matches selected filters and uses `YYYY-MM` periods. | Ready |
| `OFF-010` | Health official can view decomposition results. | Should | Decomposition outputs | View displays trend, seasonal, residual, and series status where available. | Ready |
| `OFF-011` | Health official can ask an AI assistant to explain analytics. | Could | LLM service, approved knowledge base | Assistant identifies data period, model context, limitations, and avoids diagnosis claims. | Deferred |

## Administration

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `ADM-001` | System administrator can manage official users and roles. | Must | Authentication, authorization | Administrator can create, disable, and assign allowed roles. | Proposed |
| `ADM-002` | System administrator can manage approved facility records. | Should | Facility datastore | Create, update, deactivate, and audit facility changes. | Proposed |
| `ADM-003` | System administrator can review audit events. | Must | Audit datastore | Login, data change, export, and administrative actions are searchable. | Proposed |
| `ADM-004` | System administrator can configure alert thresholds. | Should | Configuration service | Threshold change is validated, saved, and audited. | Proposed |

## Data and Analytics

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `DATA-001` | System normalizes source periods to `YYYY-MM`. | Must | Backend pipeline | CSV, API, database, charts, and exports use one period format. | Ready |
| `DATA-002` | System validates expected Region XII model locations before a run. | Must | Historical data | Run fails clearly when expected locations are missing or duplicated. | Ready |
| `DATA-003` | System validates boundary geometry and municipality matching. | Must | GeoJSON, boundary loader | Invalid or unmatched geometry produces actionable validation output. | Ready |
| `DATA-004` | System labels historical values separately from forecast scenarios. | Must | Forecast pipeline | UI and exports distinguish observed data from forecast data. | Ready |
| `DATA-005` | System records model run metadata. | Must | Model artifacts, output store | Output identifies model, configuration, run ID, and source period. | Proposed |
| `DATA-006` | System preserves last valid run when a new run fails. | Must | Run manager, output store | Failed run cannot overwrite previously valid output. | Proposed |
| `DATA-007` | Public responses contain aggregate data only. | Must | API authorization | Public response contains no individual case or sensitive user records. | Ready |

## Security and Privacy

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `SEC-001` | Protected endpoints enforce authorization server-side. | Must | Auth middleware | Changing client-side route state cannot bypass access control. | Proposed |
| `SEC-002` | Privileged accounts use strong authentication and MFA where supported. | Must | Identity provider | Privileged login meets configured authentication policy. | Proposed |
| `SEC-003` | Sensitive actions generate audit events. | Must | Audit datastore | Authentication, exports, data changes, and role changes create events. | Proposed |
| `SEC-004` | Risk-assessment answers are not stored without explicit consent. | Must | Consent service, risk feature | Anonymous assessment leaves no identifying record by default. | Deferred |
| `SEC-005` | API exposes approved origins only. | Must | API configuration | Requests from unapproved browser origins are rejected or not authorized. | Proposed |
| `SEC-006` | API errors do not expose internal exception details. | Must | API error handler | Client receives safe error message; server retains diagnostic log. | Proposed |
| `SEC-007` | Public content and AI guidance use stigma-safe language. | Must | Content review | Reviewed content avoids diagnosis claims, blame, and discriminatory wording. | Ready |

## Accessibility and Usability

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `UX-001` | Core public and official flows support keyboard navigation. | Must | Frontend | All interactive controls are reachable and operable by keyboard. | Proposed |
| `UX-002` | Risk and alert states use text or icons in addition to color. | Must | UI color system | State remains understandable without color perception. | Ready |
| `UX-003` | Core screens support responsive mobile layouts. | Must | Frontend | Home, education, locator, login, dashboard, and map remain usable on mobile. | Proposed |
| `UX-004` | Loading, empty, stale, unavailable, and error states are visible. | Must | Frontend, API | Each core data view has a clear non-success state. | Proposed |
| `UX-005` | Public health content uses plain language. | Must | Content review | User testing or editorial review confirms understandable wording. | Ready |
| `UX-006` | Maps, charts, and awareness imagery have accessible alternatives. | Must | Frontend | Meaningful visual data has labels, legends, summaries, or alt text. | Proposed |

## Operations and Release

| ID | Requirement | Priority | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|
| `OPS-001` | Backend package verification passes before release. | Must | `scripts/verify_package.py` | Verification completes without error. | Ready |
| `OPS-002` | API exposes a health-check endpoint. | Must | API service | Health endpoint reports service and data-run status. | Proposed |
| `OPS-003` | Deployment documents supported Python and dependency versions. | Must | Environment files | Clean setup succeeds using documented versions. | Proposed |
| `OPS-004` | Deployment documents boundary cache and external data behavior. | Should | Boundary loader | Operator knows online, cached, fallback, and failure behavior. | Proposed |
| `OPS-005` | Core browser flows have smoke tests. | Must | Frontend, test runner | Public education, facility search, login, dashboard, map, and export flows pass. | Proposed |

## Traceability Notes

- Backend-ready requirements describe existing `arcHIVe-main` outputs, not complete frontend behavior.
- `Age Distribution`, `Sex Distribution`, individual case records, facility capacity, and notifications remain outside MVP until source data and services exist.
- LLM assistant and anonymous AI risk assessment remain deferred until safety, consent, approved content, and service boundaries are specified.
