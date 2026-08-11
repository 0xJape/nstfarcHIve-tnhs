# ARCHIVE User Roles and Permissions

## Principles

- Least privilege by default.
- Server-side authorization is mandatory.
- Public users see aggregate, approved information only.
- Sensitive actions create audit events.
- Roles describe permissions, not job titles.
- Access to personal or sensitive data requires explicit business need.

## Roles

ARCHIVE uses two roles for MVP:

1. `user`
2. `administrator`

`user` includes public visitors and people living with HIV (PLHIV). PLHIV is a user context, not a separate permission role. The system must never require or expose HIV status to assign this role.

### User

Public or registered person using public ARCHIVE features.

| Permission | Access |
|---|---|
| View home and about pages | Allow |
| View approved HIV education | Allow |
| Search approved facilities | Allow |
| View aggregate public statistics | Allow |
| Submit general inquiry | Allow, validated |
| Use anonymous risk assessment | Future, no storage by default |
| Use public AI assistant | Future, safety constrained |
| View individual case data | Deny |
| View administrator dashboard | Deny |
| Change system settings | Deny |
### Administrator

Technical owner of accounts, roles, configuration, and operational controls.

| Permission | Access |
|---|---|
| Manage official users | Allow, audited |
| Assign approved roles | Allow, audited |
| Disable or restore accounts | Allow, audited |
| Reset account recovery flow | Allow, audited |
| Manage facility records | Allow, audited |
| Configure alert thresholds | Allow, audited |
| Review audit logs | Allow |
| Manage system settings | Allow, audited |
| View analytics | Allow where needed |
| Read user passwords or secrets | Deny |
| Delete audit records | Deny by default |
| Access individual health records | Deny by default |

## Permission Catalog

Use stable permission names in authorization code:

- `public.content.read`
- `public.facilities.read`
- `public.statistics.read`
- `public.inquiry.create`
- `profile.self.read`
- `profile.self.update`
- `analytics.dashboard.read`
- `analytics.map.read`
- `analytics.forecast.read`
- `analytics.hotspots.read`
- `analytics.municipality.read`
- `analytics.alerts.read`
- `analytics.alerts.acknowledge`
- `analytics.reports.export`
- `analytics.interventions.read`
- `facilities.directory.read`
- `facilities.directory.update`
- `content.draft.write`
- `content.publish`
- `users.manage`
- `roles.assign`
- `settings.manage`
- `audit.read`

## Default Role Matrix

| Permission group | User | Administrator |
|---|---:|---:|
| Public content | Read | Read/write |
| Public facilities | Read | Read/write |
| Aggregate analytics | Deny | Read |
| Forecasts and hotspots | Deny | Read |
| Report export | Deny | Read |
| Alert acknowledgement | Deny | Write |
| User management | Deny | Write |
| Role assignment | Deny | Write |
| System settings | Deny | Write |
| Audit logs | Deny | Read |

## Authorization Rules

1. Check permissions on every protected API request.
2. Do not rely on hidden navigation or frontend route guards.
3. Scope writes to assigned region or organization where applicable.
4. Log actor, action, target, timestamp, result, and request identifier.
5. Do not place sensitive data in URLs, browser storage, or analytics events.
6. Deny access when role, account, or permission is missing.
7. Recheck authorization during long-running exports and background jobs.
8. Separate content approval from content authorship when practical.
9. Keep administrator break-glass access disabled until needed and audit its use.
10. Review role assignments regularly.

## MVP Role Set

Start with two roles:

1. `user`
2. `administrator`

Add finer roles only when real permission boundaries require them.

## Open Decisions

- Whether health officials are scoped by province, municipality, or Region XII.
- Whether facility corrections require approval before publication.
- Whether executive exports require secondary approval.
- Retention period for inquiry records.
- Identity provider and MFA method.
- Whether users need accounts for saved resources or inquiries.
