import type { FeatureCollection, Geometry } from 'geojson'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765'

export type Health = {
  status: string
  api_version: string
  run_available: boolean
  database_available: boolean
}

export type DateRow = { PERIOD: string }

export type TestingCenter = {
  PSGC?: string
  PROVINCE?: string
  LOCATION: string
  RECOMMENDED_ADDITIONAL_CENTERS?: number
  TESTING_CENTER_NEED_SCORE?: number
}

export type MunicipalityGeometry = FeatureCollection<Geometry, {
  PSGC: string
  LOCATION: string
  PROVINCE: string
}>

export type RankingRow = Pick<SnapshotRow, 'PERIOD' | 'PSGC' | 'PROVINCE' | 'LOCATION'> & { VALUE: number }
export type AlertRow = SnapshotRow & { ALERT_TYPE?: string; ALERT_LEVEL?: string }
export type RegionSummaryRow = { PERIOD: string; [key: string]: string | number | null }
export type Metadata = Record<string, unknown>

export type SnapshotRow = {
  PERIOD: string
  PSGC: string
  PROVINCE: string
  LOCATION: string
  PREDICTED_CASES?: number
  ROLLING_12M_CASES?: number
  TRANSMISSION_PRESSURE_INDEX?: number
  HOTSPOT_CLASS?: string
  TESTING_CENTER_NEED_SCORE?: number
}
export type MunicipalityDecomposition = SnapshotRow & { TREND_COMPONENT?: number; SEASONAL_COMPONENT?: number; RESIDUAL_COMPONENT?: number }
export type MunicipalityCompartments = SnapshotRow & { TOTAL_PLHIV?: number; PLHIV_UNDIAGNOSED?: number; PLHIV_DIAGNOSED_NOT_ON_ART?: number; PLHIV_ON_ART_UNSUPPRESSED?: number; PLHIV_VIRALLY_SUPPRESSED?: number }
export type PatientSummary = { patient_code: string; care_status: string; preferred_channel: 'email' | 'sms'; municipality: string; age_group: string; treatment_status: string; created_at: string }
export type PatientIntake = { email?: string; phone?: string; preferred_channel: 'email' | 'sms'; email_consent: boolean; sms_consent: boolean; municipality: string; age_group: string; diagnosis_date?: string; treatment_status: string; referral_notes?: string }
export type Facility = { facility_code: string; name: string; facility_type: string; municipality: string; province: string; address?: string; latitude?: number; longitude?: number; services: string; opening_hours: string; phone?: string; email?: string; contact_people?: string; active?: boolean; verified_on?: string }
export type Municipality = { PSGC: string; LOCATION: string; PROVINCE: string }
export type HistoricalRow = { PERIOD: string; PSGC: string; LOCATION: string; PROVINCE: string; REPORTED_HIV_CASES: number; ROLLING_12M_CASES: number; CASES_PER_100K: number; SIX_MONTH_GROWTH_PCT: number; ACTIVE_TESTING_CENTERS: number; FACILITY_NEED_SCORE: number; SOURCE: string }
export type SampleTrendRow = { YEAR: string; CATEGORY: string; CASES: number; SOURCE: string }
export type PreRegistration = { municipality: string; preferred_channel: 'email' | 'sms'; contact_value: string; email: string; phone: string; consent: boolean; facility_code: string }
export type PendingRequest = { reference_code: string; municipality: string; preferred_channel: 'email' | 'sms'; contact_value?: string; email?: string; phone?: string; status: string; created_at: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem('archive-auth-token')
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { ...init?.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) } })
  if (!response.ok) { const result = await response.json().catch(() => ({})) as { error?: string }; throw new Error(result.error || `API request failed (${response.status})`) }
  return response.json() as Promise<T>
}

const get = <T,>(path: string) => request<T>(path)

export const api = {
  tts: async (text: string) => { const response = await fetch(`${API_BASE_URL}/api/public/tts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) }); if (!response.ok) throw new Error('Speech service unavailable'); return URL.createObjectURL(await response.blob()) },
  chat: (message: string, history: { role: 'user' | 'assistant'; content: string }[] = []) => request<{ reply: string }>('/api/public/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, history }) }),
  login: async (username: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })
    if (!response.ok) throw new Error('Invalid credentials')
    const result = await response.json() as { token: string }
    sessionStorage.setItem('archive-auth-token', result.token)
  },
  health: () => get<Health>('/api/health'),
  metadata: () => get<Metadata>('/api/metadata'),
  dates: () => get<DateRow[]>('/api/dates'),
  historicalTrend: (psgc = '') => get<HistoricalRow[]>(`/api/public/historical-cases${psgc ? `?psgc=${encodeURIComponent(psgc)}` : ''}`),
  hivSample: (group: 'AGE BRACKET' | 'GENDER', municipality = '') => get<SampleTrendRow[]>(`/api/public/hiv-sample?group=${encodeURIComponent(group)}${municipality ? `&municipality=${encodeURIComponent(municipality)}` : ''}`),
  snapshot: (period: string) =>
    get<SnapshotRow[]>(`/api/snapshot?period=${encodeURIComponent(period)}`),
  testingCenters: () => get<TestingCenter[]>('/api/testing-centers'),
  geometry: () => get<MunicipalityGeometry>('/api/geometry/municipalities'),
  ranking: (period: string, metric: string) => get<RankingRow[]>(`/api/ranking?period=${encodeURIComponent(period)}&metric=${encodeURIComponent(metric)}&limit=49`),
  timeline: (psgc: string) => get<SnapshotRow[]>(`/api/timeline?psgc=${encodeURIComponent(psgc)}`),
  decomposition: (location: string) => get<MunicipalityDecomposition[]>(`/api/decomposition?location=${encodeURIComponent(location)}`),
  compartments: (location: string) => get<MunicipalityCompartments[]>(`/api/compartments?location=${encodeURIComponent(location)}`),
  alerts: () => get<AlertRow[]>('/api/alerts?limit=50'),
  regionSummary: () => get<RegionSummaryRow[]>('/api/region-summary'),
  patients: () => get<PatientSummary[]>('/api/admin/patients'),
  createPatient: (patient: PatientIntake) => request<{ patient_code: string; care_status: string }>('/api/admin/patients', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patient) }),
  facilities: () => get<Facility[]>('/api/admin/facilities'),
  publicFacilities: () => get<Facility[]>('/api/public/facilities'),
  municipalities: () => get<Municipality[]>('/api/municipalities'),
  submitPreRegistration: (payload: PreRegistration) => request<{ reference_code: string; status: string }>('/api/pre-registrations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  confirmPreRegistration: (referenceCode: string, token: string) => request<{ reference_code: string; status: string; handoff_status: string }>(`/api/pre-registrations/${encodeURIComponent(referenceCode)}/confirm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) }),
  pendingRequests: () => get<PendingRequest[]>('/api/admin/pre-registrations'),
  reviewRequest: (referenceCode: string, decision: 'accept' | 'reject') => request<{ status: string; patient_code?: string }>(`/api/admin/pre-registrations/${encodeURIComponent(referenceCode)}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision }) }),
  deleteRequest: (referenceCode: string) => request<{ status: string }>(`/api/admin/pre-registrations/${encodeURIComponent(referenceCode)}/delete`, { method: 'POST' }),
  dispatchWebhooks: () => request<{ queued: number; sent: number; failed: number }>('/api/admin/webhooks/dispatch', { method: 'POST' }),
  assignPatient: (patientCode: string, facilityCode: string) => request<{ assignment_id: string }>('/api/admin/patients/' + encodeURIComponent(patientCode) + '/assignments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ facility_code: facilityCode }) }),
}
