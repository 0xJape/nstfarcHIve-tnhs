# Care facility import contract

Replace template row in `care_facilities.template.csv` with verified records. Required fields: `facility_id`, `name`, `facility_type`, `address`, `municipality`, `province`, `psgc`, `services`, `source_url`, `verified_on`.

Allowed `facility_type`: `testing_center`, `treatment_hub`, `hospital`, `rhu`, `community_organization`.

Coordinates must be decimal WGS84. `verified_on` must use `YYYY-MM-DD`. Do not publish unverified records. Current `/api/testing-centers` route contains planning recommendations, not facility locations.
