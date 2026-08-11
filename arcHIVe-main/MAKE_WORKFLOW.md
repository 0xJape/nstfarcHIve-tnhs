# Make patient referral workflow

ARCHIVE owns consent and confirmation. Make only delivers messages and forwards confirmed details.

## Required environment

- `MAKE_WEBHOOK_URL`: Make custom webhook URL.
- `ARCHIVE_PUBLIC_URL`: Public frontend origin, for example `https://archive.example.org`. Do not use localhost outside development.

## Scenario

1. Add **Webhooks > Custom webhook** as trigger.
2. Add router using `event_type`.

### Route 1 — `registration.ticket_requested`

Triggered after administrator accepts request.

1. Filter: `event_type` equals `registration.ticket_requested`.
2. Branch on `preferred_channel`:
   - `email`: send discreet email to `patient_email`.
   - `sms`: send discreet SMS to `patient_phone`.
3. Message must include:
   - Reference: `reference_code`
   - Selected center: `facility.name`
   - Confirmation link: `confirmation_url`
4. Do not put HIV, diagnosis, or medical details in email subject or SMS preview.

Suggested subject: `Your ARCHIVE request is ready`

Suggested body:

> Your private ARCHIVE request {{reference_code}} was reviewed. Confirm that ARCHIVE may forward your submitted contact details to {{facility.name}}: {{confirmation_url}}. Ignore this message if you did not submit this request.

### Route 2 — `registration.referral_confirmed`

Triggered only after patient opens ARCHIVE link and explicitly confirms.

1. Filter: `event_type` equals `registration.referral_confirmed`.
2. Require non-empty `facility.email`; otherwise stop and alert administrator.
3. Send email to `facility.email` containing only necessary referral data:
   - Reference: `reference_code`
   - Municipality: `municipality`
   - Preferred channel: `preferred_channel`
   - Email: `patient_email`, when present
   - Phone: `patient_phone`, when present
4. Do not infer or include diagnosis, HIV status, symptoms, or risk.
5. Use `idempotency_key` as Make data-store key. Stop duplicate deliveries.

Suggested subject: `New consented ARCHIVE care referral — {{reference_code}}`

Suggested body:

> Patient confirmed forwarding of submitted contact details through ARCHIVE.
>
> Reference: {{reference_code}}
> Municipality: {{municipality}}
> Preferred contact: {{preferred_channel}}
> Email: {{patient_email}}
> Mobile: {{patient_phone}}
>
> Please handle all follow-up under your center's privacy and care procedures.

## Dispatch

Current backend queues events in `webhook_outbox`. Call authenticated `POST /api/admin/webhooks/dispatch` after review and periodically with a scheduler. Recommended production interval: one minute.

## Data boundary

After confirmed referral reaches selected center, center owns follow-up. ARCHIVE retains audit/status records required for delivery integrity; it does not manage clinical care.
