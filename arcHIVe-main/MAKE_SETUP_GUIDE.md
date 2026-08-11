# ARCHIVE Make setup — exact mapping

## Goal

```text
Admin accepts request
    ↓
Make emails patient confirmation link
    ↓
Patient clicks Continue
    ↓
ARCHIVE queues confirmed referral
    ↓
Make emails selected center
```

Center receives patient details only after patient confirmation.

---

## 1. Create webhook

In Make:

1. Create a new scenario.
2. Add **Webhooks → Custom webhook**.
3. Create webhook: `ARCHIVE referral events`.
4. Copy webhook URL.
5. Click **Run once** and leave Make waiting.

In `arcHIVe-main/.env`:

```dotenv
MAKE_WEBHOOK_URL=https://hook.make.com/your-webhook-id
ARCHIVE_PUBLIC_URL=http://127.0.0.1:5173
```

Restart backend after editing `.env`.

`127.0.0.1` works only on this computer. Use public HTTPS URL when sending links to other people.

---

## 2. Capture first sample

1. Start ARCHIVE backend and frontend.
2. Submit test request using email.
3. Open admin page.
4. Accept request.
5. Confirm Make receives webhook bundle.

Use test data only.

Expected event value:

```text
registration.ticket_requested
```

If fields do not appear in Make mapping panel, capture sample again before adding Gmail.

---

## 3. Build scenario shape

After webhook, add one **Router**:

```text
[1] Webhooks — Custom webhook
        │
        └── [2] Router
              ├── Route A: Patient confirmation email
              │       └── [3] Gmail — Send an email
              └── Route B: Confirmed center referral
                      └── [4] Gmail — Send an email
```

Do not connect Route B directly to `registration.ticket_requested`.

---

## 4. Route A — patient email

### Filter

Click Route A filter and set:

| Filter field | Operator | Value |
|---|---|---|
| `event_type` | Equal to | `registration.ticket_requested` |
| `preferred_channel` | Equal to | `email` |
| `patient_email` | Exists / is not empty | — |

Join conditions with **AND**.

### Gmail module

Add **Gmail → Send an email**.

#### Recipient

| Gmail field | Select from webhook |
|---|---|
| **To** | `patient_email` |

Click the field and select the value from Make's mapping panel. Do not type a test address.

#### Subject

Type exactly:

```text
Your ARCHIVE request is ready
```

#### Body type

Select **HTML**.

Paste this template, then replace every `{{...}}` item by selecting the matching field from Make mapping panel:

```html
<div style="margin:0;background:#f4f1ec;padding:32px 16px;font-family:Arial,sans-serif;color:#243238;">
  <div style="max-width:560px;margin:auto;background:#ffffff;border:1px solid #d8c7ca;border-radius:16px;overflow:hidden;">
    <div style="height:6px;background:#a72935;"></div>
    <div style="background:#281217;padding:26px 30px;color:#ffffff;">
      <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#f4c8cc;">ARCHIVE · Region XII</div>
      <h1 style="margin:10px 0 0;font-size:25px;font-weight:600;">Your request was reviewed</h1>
    </div>
    <div style="padding:30px;line-height:1.6;">
      <p style="margin-top:0;">Your private ARCHIVE request <strong>{{2.reference_code}}</strong> is ready for your confirmation.</p>
      <div style="margin:24px 0;padding:18px 20px;background:#f8edef;border-left:4px solid #a72935;border-radius:8px;">
        <div style="font-size:12px;color:#667579;text-transform:uppercase;letter-spacing:1px;">Selected center</div>
        <div style="margin-top:5px;font-size:18px;font-weight:600;">{{2.facility.name}}</div>
      </div>
      <p>By clicking <strong>Continue</strong>, you allow authorized officials from {{2.facility.name}} to contact you using the details you submitted to book and schedule an appointment.</p>
      <p>If you do not wish to provide or forward your personal details, we respect that choice.</p>
      <p style="margin:28px 0;text-align:center;"><a href="{{2.confirmation_url}}" style="display:inline-block;background:#a72935;color:#ffffff;text-decoration:none;padding:13px 24px;border-radius:999px;font-weight:600;">Continue</a></p>
      <p style="font-size:13px;color:#667579;">Ignore this message if you did not submit this request.</p>
    </div>
    <div style="padding:18px 30px;background:#f8edef;color:#62595b;font-size:12px;">ARCHIVE · Private care navigation</div>
  </div>
</div>
```

### Patient email mapping

| Template item | Webhook field |
|---|---|
| `{{reference_code}}` | `reference_code` |
| `{{facility.name}}` | Expand `facility` → `name` |
| `{{confirmation_url}}` | `confirmation_url` |

Make fields must appear as colored mapping tokens. With your webhook as module `2`, the tokens look like `{{2.reference_code}}`, `{{2.facility.name}}`, and `{{2.confirmation_url}}`. Do not type these manually; select fields from Make's mapping panel.

---

## 5. Route B — confirmed center email

This route receives only `registration.referral_confirmed`.

### Filter

| Filter field | Operator | Value |
|---|---|---|
| `event_type` | Equal to | `registration.referral_confirmed` |
| `facility.email` | Exists / is not empty | — |

Join conditions with **AND**.

### Gmail module

Add **Gmail → Send an email**.

#### Recipient mapping

### Temporary testing recipient

For now, send confirmed referrals to your own email:

| Gmail field | Temporary value |
|---|---|
| **To** | Type your own email address, for example `yourname@example.com` |

Do not map `patient_email` here. Do not use a patient's email as center recipient.

When real care-center email addresses are ready, replace your fixed address with:

| Gmail field | Production mapping |
|---|---|
| **To** | Expand `facility` → select `email` |

Keep Route B filter requiring `facility.email` to exist. During temporary testing, this filter may block the route if the sample has no center email. Use a separate temporary filter only if needed:

```text
event_type = registration.referral_confirmed
```

Restore the production filter before going live:

```text
event_type = registration.referral_confirmed
AND facility.email exists / is not empty
```

| Gmail field | Select from webhook |
|---|---|
| **To** | Expand `facility` → select `email` |

Never select `patient_email` for this module.

#### Subject mapping

Type:

```text
New consented ARCHIVE care referral — 
```

Then insert mapped field `reference_code` after the space.

Final subject:

```text
New consented ARCHIVE care referral — {{2.reference_code}}
```

#### Body type

Select **HTML**. Use this body:

```html
<div style="margin:0;background:#f4f1ec;padding:32px 16px;font-family:Arial,sans-serif;color:#243238;">
  <div style="max-width:600px;margin:auto;background:#ffffff;border:1px solid #d8c7ca;border-radius:16px;overflow:hidden;">
    <div style="height:6px;background:#a72935;"></div>
    <div style="background:#281217;padding:26px 30px;color:#ffffff;">
      <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#f4c8cc;">ARCHIVE · Region XII</div>
      <h1 style="margin:10px 0 0;font-size:25px;font-weight:600;">Confirmed care referral</h1>
    </div>
    <div style="padding:30px;line-height:1.6;">
      <p style="margin-top:0;">The patient confirmed that authorized center officials may contact them to book and schedule an appointment.</p>
      <table style="width:100%;border-collapse:collapse;margin:24px 0;">
        <tr><td style="padding:10px 0;border-bottom:1px solid #eee;color:#667579;">Reference</td><td style="padding:10px 0;border-bottom:1px solid #eee;text-align:right;font-weight:600;">{{2.reference_code}}</td></tr>
        <tr><td style="padding:10px 0;border-bottom:1px solid #eee;color:#667579;">Municipality</td><td style="padding:10px 0;border-bottom:1px solid #eee;text-align:right;">{{2.municipality}}</td></tr>
        <tr><td style="padding:10px 0;border-bottom:1px solid #eee;color:#667579;">Preferred contact</td><td style="padding:10px 0;border-bottom:1px solid #eee;text-align:right;">{{2.preferred_channel}}</td></tr>
        <tr><td style="padding:10px 0;border-bottom:1px solid #eee;color:#667579;">Email</td><td style="padding:10px 0;border-bottom:1px solid #eee;text-align:right;">{{2.patient_email}}</td></tr>
        <tr><td style="padding:10px 0;color:#667579;">Mobile</td><td style="padding:10px 0;text-align:right;">{{2.patient_phone}}</td></tr>
      </table>
      <p style="font-size:13px;color:#667579;">Please handle contact and appointment scheduling under your center's privacy and care procedures.</p>
    </div>
    <div style="padding:18px 30px;background:#f8edef;color:#62595b;font-size:12px;">ARCHIVE · Consent-based referral handoff</div>
  </div>
</div>
```

### Center email mapping

| Template item | Webhook field |
|---|---|
| `{{reference_code}}` | `reference_code` |
| `{{municipality}}` | `municipality` |
| `{{preferred_channel}}` | `preferred_channel` |
| `{{patient_email}}` | `patient_email` |
| `{{patient_phone}}` | `patient_phone` |

---

## 6. Test exact flow

1. Make: click **Run once**.
2. Submit test request using email.
3. Admin accepts request.
4. Patient email arrives.
5. Confirm center email does **not** arrive.
6. Open patient email and click **Continue**.
7. Confirmation page appears.
8. Click **Continue** there.
9. Center email arrives.
10. Check Make history shows:

```text
registration.ticket_requested
registration.referral_confirmed
```

11. Open confirmation link again. It must fail because token is one-time.

If center receives email before step 8, stop scenario and check Route B filter.

---

## 7. Turn scenario on

Only after test passes:

1. Save scenario.
2. Set schedule to **Immediately as data arrives**.
3. Turn scenario **ON**.

Use real public HTTPS URL in `ARCHIVE_PUBLIC_URL` before sending links outside your computer.

Never include diagnosis, HIV status, symptoms, risk score, or model output in either email.
