# ARCHIVE MVP Requirements Scheme

## Requirement ID Format

Use IDs by domain:

- `PUB-###` — public experience
- `OFF-###` — health-official experience
- `ADM-###` — administration
- `DATA-###` — data and analytics
- `SEC-###` — security and privacy
- `UX-###` — accessibility and usability
- `OPS-###` — operations and release

## Requirement Record

Each requirement uses this structure:

| Field | Meaning |
|---|---|
| ID | Stable requirement identifier |
| Requirement | Testable behavior |
| Priority | Must, Should, or Could |
| User | Role that needs it |
| Source | Design, stakeholder, backend, policy, or research |
| Dependency | API, dataset, service, or role dependency |
| Acceptance test | Observable pass condition |
| Status | Proposed, Ready, In progress, Verified, Deferred |

## Priority Rules

- **Must:** MVP cannot release without it.
- **Should:** Important; release may proceed with documented workaround.
- **Could:** Useful later; not release-blocking.
- **Deferred:** Explicitly outside current release.

## Requirement Examples

| ID | Requirement | Priority | User | Dependency | Acceptance test | Status |
|---|---|---|---|---|---|---|
| `PUB-001` | Visitor can browse approved HIV education pages without login. | Must | Public visitor | Content service | Page opens without authentication and shows approved content. | Proposed |
| `PUB-002` | Visitor can search approved testing facilities by location. | Must | Public visitor | Facility data, map service | Search returns matching facilities with contact details. | Proposed |
| `OFF-001` | Health official can view latest analytics run after authentication. | Must | Health official | Auth, backend API | Unauthenticated request fails; authorized request returns run summary. | Proposed |
| `OFF-002` | Health official can inspect municipality forecast scenarios. | Must | Health official | Forecast API | Selected municipality shows period, value, model run, and scenario label. | Proposed |
| `DATA-001` | System stores and displays periods as `YYYY-MM`. | Must | All | Backend pipeline | API, tables, charts, and exports use same period format. | Ready |
| `SEC-001` | Public endpoints expose aggregate data only. | Must | Public visitor | API authorization | Individual or sensitive records never appear in public response. | Proposed |
| `UX-001` | Risk and alert states use text plus visual indicators. | Must | All | Design system | Color-blind user can identify state from label/icon. | Ready |
| `OPS-001` | Failed model run cannot replace last valid run. | Must | Administrator | Run manager, storage | Failed run remains visible as failed and prior valid run remains available. | Proposed |

## Traceability Scheme

Every feature must link through this chain:

`Requirement ID → User flow → Screen/API → Data field → Acceptance test`

Example:

`OFF-002 → Municipality profile flow → /municipalities/{id} → forecast values → forecast scenario test`

## Status Definitions

- **Proposed:** Identified but not reviewed.
- **Ready:** Scope, dependency, and acceptance test defined.
- **In progress:** Implementation started.
- **Verified:** Acceptance test passed.
- **Deferred:** Moved outside current release.
- **Rejected:** Not included in product.

## Review Rules

Before marking `Ready`:

1. Requirement describes one behavior.
2. User and priority are named.
3. Data and API dependencies are known.
4. Acceptance test is observable.
5. Privacy impact is identified.
6. Requirement fits `MVP_SCOPE.md`.

Before marking `Verified`:

1. Backend verification passes.
2. API response is checked.
3. UI flow is checked where applicable.
4. Error and empty states are checked.
5. Evidence is recorded in the test report.
