# ARCHIVE Product Update Plan

## Update Goal

Extend ARCHIVE beyond HIV surveillance dashboards into a compassionate, multilingual public-health companion while preserving privacy, aggregate analytics, accessibility, and non-diagnostic wording.

## Requested Updates

1. Multilingual AI chatbot.
2. Spoken chatbot responses using browser text-to-speech, with mute and replay controls.
3. Non-stigmatizing color palette refresh.
4. ARCHIVE–DOH Intervention Calendar and timeline.
5. Intervention-to-HIV-trend map and target-population views.
6. Expanded HIV Education Center and public Support page with verified external resources, crisis contacts, privacy guidance, and FAQs.

## Product Boundaries

- ARCHIVE does not diagnose HIV, mental-health conditions, or medical emergencies.
- Chatbot output must use approved sources, state uncertainty, and direct users to qualified professionals when needed.
- Crisis, self-harm, abuse, or urgent medical language must trigger a clear emergency/support-resource response, not automated clinical advice.
- Public analytics remain aggregate and must not expose individual health records.
- No user wellness/medical dashboard or personal wellness tracking is in current scope.
- Voice is optional. No audio recording or voice storage in first release.

## Recommended Delivery Order

### Phase 0 — Product and Safety Foundation

- Confirm supported languages and translation owners.
- Define chatbot knowledge sources, escalation rules, and prohibited claims.
- Define intervention data ownership, approval status, and update workflow with DOH stakeholders.
- Verify education sources, support providers, hotline availability, and review dates before release.
- Create event taxonomy for analytics without storing sensitive free text by default.

### Phase 1 — Design System Refresh

- Replace Awareness Crimson as dominant UI color.
- Use calm teal/blue, warm sand, slate, and accessible status colors.
- Keep semantic status labels and icons; never use color alone for risk or urgency.
- Update `UI_UX_COLOR_SYSTEM.md`, frontend CSS tokens, charts, maps, buttons, alerts, and focus states.
- Validate WCAG 2.2 AA contrast and reduced-motion behavior.

### Phase 2 — Multilingual Chatbot

- Add a chatbot surface to the public portal.
- Add language selector and persist preference locally; do not infer sensitive identity from language.
- Use approved multilingual content and preserve medical terms accurately.
- Add source references, disclaimer, feedback, clear-chat, and report-response actions.
- Add text-to-speech with browser `speechSynthesis`:
  - Play, pause, stop, replay, mute.
  - Select available voice for chosen language.
  - Show text transcript alongside audio.
  - Respect reduced motion and accessibility settings.
  - Never auto-play audio.
- Keep chatbot out of diagnosis, treatment prescription, and emergency triage.

### Phase 3 — DOH Intervention Calendar

- Add intervention records with:
  - Title and description.
  - Intervention type.
  - Start/end date.
  - Province/municipality and coordinates or PSGC.
  - Target population.
  - Implementing organization.
  - Status: planned, active, completed, cancelled.
  - Evidence/source link.
  - Approval and last-updated metadata.
- Add calendar, chronological timeline, filters, and intervention detail view.
- Overlay intervention periods against historical and forecast HIV trends.
- Add map layers for intervention locations and aggregate trend indicators.
- Make causal claims impossible by default: label overlays as temporal/spatial comparison, not proof of intervention effect.
- Add empty, stale, unavailable, and unapproved-data states.

### Phase 4 — Education and Support

- Expand education into seven source-linked topics: basics, testing, prevention, PrEP/PEP, treatment/U=U, rights, and myths.
- Add public support pathways for HIV care, community connection, and emotional support.
- Add verified provider links, crisis contacts, privacy guidance, and FAQs.
- Show review caveats because external services, schedules, eligibility, and hotlines can change.
- Keep existing ARCHIVE care-booking workflow separate from external provider links.

### Phase 5 — Validation and Release

- Test supported languages with public-health reviewers.
- Test chatbot refusal, escalation, hallucination, and source-link behavior.
- Test text-to-speech availability and fallback when no matching voice exists.
- Test calendar filtering, date boundaries, map overlays, and stale data.
- Test external links, keyboard navigation, responsive layouts, and urgent-support wording.
- Run accessibility, security, API, browser, and mobile smoke tests.
- Update deployment and rollback documentation.

## Proposed API Additions

All routes require final security review before implementation.

| Method | Route | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/interventions` | Approved intervention records with filters | Public/aggregate |
| `GET` | `/api/interventions/timeline` | Timeline-ready intervention and trend data | Public/aggregate |
| `GET` | `/api/interventions/{id}` | Approved intervention detail | Public/aggregate |
| `POST` | `/api/chat` | Generate response from approved knowledge sources | Public, rate-limited |
| `GET` | `/api/chat/sources` | Return source metadata used by chatbot | Public |
| `GET` | `/api/resources` | Verified support and care resources | Public |
Current read-only SQLite analytics can remain unchanged for Phase 1–4. Mutable intervention, account, resource, audit, and chatbot-feedback records should use PostgreSQL or another production database before launch.

## Frontend Work Areas

- `archive-frontend/src/App.tsx`: route/navigation integration.
- `archive-frontend/src/App.css` and `archive-frontend/src/index.css`: palette and accessibility tokens.
- New chatbot page/component: multilingual transcript and speech controls.
- New intervention calendar/timeline/map components.
- New education and support page components.
- `archive-frontend/src/api.ts`: typed API calls and error states.
- `API_CONTRACT.md`: endpoint and response updates.
- `USER_ROLES_AND_PERMISSIONS.md`: intervention permissions.

## Data and Security Requirements

- Use PSGC and stable intervention IDs; do not use names as primary keys.
- Validate date ranges, language codes, IDs, and pagination server-side.
- Rate-limit chatbot requests and cap prompt/response size.
- Do not store chatbot conversations by default; if opt-in storage is added, disclose retention and allow deletion.
- Log administrative intervention changes and resource verification changes.
- Keep secrets out of source control and keep approved origins restricted.

## Definition of Done

- All new UI has loading, empty, error, stale, and unavailable states.
- Language selection works for supported text content; unsupported content falls back clearly.
- Chatbot always shows transcript, sources where applicable, and medical disclaimer.
- Speech never starts without user action.
- Intervention calendar, timeline, and map agree on filters and dates.
- Education and support pages identify external resources clearly and include review-date caveats.
- Color palette passes contrast checks and avoids stigmatizing or alarmist presentation.
- API, accessibility, security, and browser smoke checks pass.
- `README.md`, `API_CONTRACT.md`, deployment docs, and release notes are updated.

## First Implementation Slice

1. Refresh color tokens and shared components.
2. Add intervention data contract and read-only calendar prototype.
3. Add chatbot UI with language selection and browser speech controls using mocked approved responses.
4. Review safety wording and source display.
5. Add backend endpoints only after UI contract review.
6. Add source-linked education and support pages; skip wellness/medical dashboard.

## Decisions Needed Before Coding

- Supported launch languages: Filipino, English, or additional Region XII languages.
- Chatbot provider and approved knowledge-base owner.
- Whether chatbot responses may be generated remotely or must use a self-hosted model.
- DOH intervention data format, approval process, and update frequency.
- Exact verified resource list and emergency contacts.
