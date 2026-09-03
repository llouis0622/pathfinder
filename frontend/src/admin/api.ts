/** 관리자 API 클라이언트 (/api/admin). 세션은 pf_admin 쿠키. */
import { ApiError } from '../api'
import type { Route } from '../types'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, credentials: 'include', headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) } })
  if (!res.ok) {
    let detail = `요청 실패 (${res.status})`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch { /* 본문 없음 */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)) })
  const s = p.toString()
  return s ? `?${s}` : ''
}

// ---------------------------------------------------------------- 타입
export type AdminMe = { configured: boolean; admin: boolean }
export type Paged<T> = { items: T[]; total: number; page: number; size: number; pages: number }
export type UserRef = { id: string; provider: string; nickname: string; avatar_url: string; created_at: string | null; last_login_at: string | null }
export type RequestRow = {
  id: string; created_at: string; user: UserRef | null; user_id: string | null; profile: string; profile_label: string
  origin: { lat: number; lng: number; name: string }; destination: { lat: number; lng: number; name: string }
  status: string; error: string | null; elapsed_ms: number | null; personalized: boolean; explored: boolean; prefer_shade: boolean
  weather_flags: string[]; departure_at: string | null; n_results: number | null; chosen_rank: number | null
}
export type AccessRow = {
  id: string; created_at: string; kind: string; method: string; path: string; status: number; duration_ms: number | null
  user: UserRef | null; user_id: string | null; ip: string; user_agent: string; detail: string | null
}
export type EngineRow = {
  id: string; created_at: string; request_id: string; profile: string; profile_label: string; origin_name: string; dest_name: string; k: number
  corridor_nodes: number; corridor_edges: number; blocked_edges: number; snap_origin_m: number | null; snap_destination_m: number | null
  aco: { iterations: number; ants_completed: number; ants_failed: number; stopped_by: string; elapsed_ms: number | null }
  ga: { enabled: boolean; generations: number; elapsed_ms: number | null }
  archive_size: number; routes_returned: number; engine_elapsed_ms: number | null; backend_elapsed_ms: number | null; shade_status: string
  weather_flags: string[]
}
export type ChoiceRow = {
  id: string; created_at: string; request_id: string; user: UserRef | null; user_id: string | null; route_id: string; shown_rank: number
  propensity: number | null; learned: boolean; origin_name: string; dest_name: string; profile: string; personalized: boolean; explored: boolean
}
export type PolicyUpdateRow = {
  id: string; created_at: string; user_id: string; request_id: string | null; route_id: string; shown_rank: number; engine_rank: number | null
  explored: boolean; updates_after: number; weights_before: Record<string, number>; weights_after: Record<string, number>
}
export type PlaceRow = { id: string; created_at: string; query: string; source: string; result_count: number }
export type Policy = { updates: number; weights: Record<string, number>; summary: string[] }
export type UserListRow = UserRef & { requests: number; choices: number; updates: number; summary: string[] }
export type UserDetail = {
  user: UserRef
  stats: { requests: number; choices: number; personalized_requests: number; policy_updates: number; rank1_choice_rate: number | null
    profiles: { profile: string; label: string; count: number }[] }
  policy: Policy & { updated_at: string | null }
  recent_requests: RequestRow[]; choices: ChoiceRow[]; policy_history: PolicyUpdateRow[]; recent_access: AccessRow[]
}
export type RequestDetail = {
  request: RequestRow; weather: Record<string, unknown> | null; options: Record<string, unknown> | null
  propensities: Record<string, number> | null; metadata: Record<string, unknown> | null
  routes: { rank: number; engine_rank: number | null; summary: string; badges: string[]; cautions: string[]; total_duration_min: number
    walk_distance_m: number; transfers: number; generalized_cost_s: number | null; payload: Route }[]
  choice: ChoiceRow | null; engine_run: EngineRow | null; policy_update: PolicyUpdateRow | null
}
export type Overview = {
  generated_at: string
  kpis: { requests_total: number; requests_today: number; requests_7d: number; users_total: number; users_new_7d: number; active_users_7d: number
    choices_7d: number; choose_rate_7d: number | null; personalized_share_7d: number | null; no_route_rate_7d: number | null
    error_rate_7d: number | null; avg_elapsed_ms_7d: number | null; learned_users: number; access_errors_24h: number }
  series: { date: string; requests: number; choices: number; users: number }[]
  profile_share: { profile: string; label: string; count: number }[]
  recent_requests: RequestRow[]; recent_auth: AccessRow[]
}
export type Usage = {
  days: number; total_requests: number
  daily: { date: string; requests: number; ok: number; no_route: number; error: number; choices: number; users: number; new_users: number }[]
  hourly: { hour: number; count: number }[]; weekday: { weekday: number; label: string; count: number }[]
  profile_share: { profile: string; label: string; count: number }[]; status_share: { status: string; count: number }[]
  prefer_shade: { on: number; off: number }; weather_flags: { flag: string; count: number }[]
  place_searches: { total: number; no_result: number; sources: { source: string; count: number }[]; top_queries: { query: string; count: number }[] }
}
export type RankStat = { rank: number; shown: number; chosen: number; rate: number | null }
export type Quality = {
  days: number; requests: number; ok: number; choices: number; choose_rate: number | null; learned_choices: number
  by_shown_rank: RankStat[]; by_engine_rank: RankStat[]
  compare: Record<'personalized' | 'plain' | 'explored', { choices: number; rank1_hit_rate: number | null }>
  per_profile: { profile: string; label: string; requests: number; no_route_rate: number | null; avg_elapsed_ms: number | null
    avg_duration_min: number | null; avg_walk_m: number | null; avg_transfers: number | null }[]
  badges: { key: string; count: number }[]; cautions: { key: string; count: number }[]
}
export type Spatial = {
  days: number; requests: number
  top_origins: { name: string; count: number; lat: number; lng: number }[]; top_destinations: { name: string; count: number; lat: number; lng: number }[]
  top_pairs: { origin: string; destination: string; count: number; no_route: number }[]
  top_stations: { name: string; count: number }[]; lines: { name: string; count: number }[]
  facilities: { facility: string; count: number }[]; unverified_stations: { name: string; count: number }[]
}
export type EngineBlock = {
  runs: number; engine_p50_ms: number | null; engine_p95_ms: number | null; backend_p50_ms: number | null; aco_p50_ms: number | null
  ga_p50_ms: number | null; avg_iterations: number | null; avg_generations: number | null; ant_fail_ratio: number | null
  avg_corridor_nodes: number | null; avg_corridor_edges: number | null; avg_blocked_edges: number | null; avg_archive: number | null
  stopped_by: { reason: string; count: number }[]
}
export type EngineStats = {
  days: number; summary: EngineBlock; per_profile: (EngineBlock & { profile: string; label: string })[]
  daily: { date: string; runs: number; p50_ms: number | null; p95_ms: number | null }[]; shade_status: { status: string; count: number }[]
}
export type Maintenance = { retention_days: number; tables: Record<string, { rows: number; oldest: string | null }> }
export type PruneResult = { days: number; deleted: Record<string, number> }
export type IpsPolicy = { matched: number; ips: number; snips: number | null; ess: number }
export type Ips = { samples: number; epsilon: number; logged_hit_rate?: number; explored?: number; days?: number; note?: string
  policies: Partial<Record<'engine' | 'personalized', IpsPolicy>> }
export type Preferences = {
  learned_users: number; total_policies: number
  per_feature: { feature: string; positive_label: string; negative_label: string; mean: number; positive_users: number; negative_users: number }[]
  labels: { label: string; count: number }[]; updates_histogram: { bucket: string; count: number }[]
  users: { user: UserRef; updates: number; weights: Record<string, number>; summary: string[]; updated_at: string | null }[]
}

// ---------------------------------------------------------------- 호출
export const adminMe = () => call<AdminMe>('/api/admin/me')
export const adminLogin = (password: string) => call<{ admin: boolean }>('/api/admin/login', { method: 'POST', body: JSON.stringify({ password }) })
export const adminLogout = () => call<{ admin: boolean }>('/api/admin/logout', { method: 'POST' })
export const fetchOverview = () => call<Overview>('/api/admin/overview')
export const fetchUsage = (days: number) => call<Usage>(`/api/admin/analytics/usage${qs({ days })}`)
export const fetchQuality = (days: number) => call<Quality>(`/api/admin/analytics/quality${qs({ days })}`)
export const fetchSpatial = (days: number) => call<Spatial>(`/api/admin/analytics/spatial${qs({ days })}`)
export const fetchEngineStats = (days: number) => call<EngineStats>(`/api/admin/analytics/engine${qs({ days })}`)
export const fetchPreferencesAll = () => call<Preferences>('/api/admin/preferences')
export const fetchMaintenance = () => call<Maintenance>('/api/admin/maintenance')
export const pruneLogs = (days?: number) => call<PruneResult>('/api/admin/maintenance/prune', { method: 'POST', body: JSON.stringify(days === undefined ? {} : { days }) })
export const fetchIps = (days: number) => call<Ips>(`/api/admin/analytics/ips${qs({ days })}`)
export const fetchRequests = (params: Record<string, string | number | boolean | undefined>) => call<Paged<RequestRow>>(`/api/admin/logs/requests${qs(params)}`)
export const fetchRequestDetail = (id: string) => call<RequestDetail>(`/api/admin/logs/requests/${id}`)
export const fetchAccess = (params: Record<string, string | number | undefined>) => call<Paged<AccessRow>>(`/api/admin/logs/access${qs(params)}`)
export const fetchEngineLogs = (params: Record<string, string | number | undefined>) => call<Paged<EngineRow>>(`/api/admin/logs/engine${qs(params)}`)
export const fetchChoices = (params: Record<string, string | number | boolean | undefined>) => call<Paged<ChoiceRow>>(`/api/admin/logs/choices${qs(params)}`)
export const fetchPolicyUpdates = (params: Record<string, string | number | undefined>) => call<Paged<PolicyUpdateRow>>(`/api/admin/logs/policy-updates${qs(params)}`)
export const fetchPlaces = (params: Record<string, string | number | undefined>) => call<Paged<PlaceRow>>(`/api/admin/logs/places${qs(params)}`)
export const fetchUsers = (params: Record<string, string | number | undefined>) => call<Paged<UserListRow> & { providers: { provider: string; count: number }[] }>(`/api/admin/users${qs(params)}`)
export const fetchUserDetail = (id: string) => call<UserDetail>(`/api/admin/users/${id}`)
export const resetUserPolicy = (id: string) => call<{ ok: boolean; reset: boolean }>(`/api/admin/users/${id}/policy`, { method: 'DELETE' })
export const exportUrl = (kind: 'requests' | 'choices' | 'users' | 'access' | 'engine', days = 30) => `/api/admin/export/${kind}.csv${qs({ days })}`

// ---------------------------------------------------------------- 운영: 데이터 품질·제보·알림
type Tri = { yes: number; no: number; unknown: number }
export type GraphStats = {
  source?: string; error?: string
  nodes?: { total: number; by_kind: Record<string, number> }
  edges?: { total: number; by_kind: Record<string, number> }
  walk?: { edges: number; length_km?: number; grade_coverage: number | null; width_coverage?: number | null; surface_coverage?: number | null
    stairs?: number; stairs_without_ramp?: number; steep_over_10pct?: number; kerbs?: Record<string, number>; crossings?: Record<string, number>; tactile?: Tri; lit?: Tri }
  vertical?: { edges?: number; elevator: Tri; escalator?: Tri }
  transit?: { stops: number; platforms: number; entrances: number; routes: number; low_floor_known: number }
  buildings?: { total: number; height_known: number; height_coverage: number | null }
  connectivity?: { components: number; largest_share: number | null; isolated_walk_nodes: number }
}
export type DataQuality = { graph: GraphStats; reports: Record<string, number>; active_overrides: number
  search_cache: { size: number; maxsize: number; hits: number; misses: number; hit_rate?: number | null; ttl_s?: number } | null }
export type ReportRow = { id: string; created_at: string; user_id: string | null; user: UserRef | null; request_id: string | null; lat: number; lng: number
  kind: string; kind_label: string; note: string; place_name: string; status: string; edge_id: number | null; edge_kind: string; admin_note: string | null; resolved_at: string | null }
export type OverrideRow = { id: string; created_at: string; edge_id: number; kind: string; kind_label: string; active: boolean; expires_at: string | null; note: string
  report_id: string | null; deactivated_at: string | null }
export type AlertRule = { enabled: boolean; threshold?: number; min_samples?: number }
export type AlertSettings = { enabled: boolean; webhook_url: string; webhook_url_masked: string; webhook_configured: boolean; format: 'slack' | 'json'
  interval_min: number; window_min: number; cooldown_min: number; rules: Record<string, AlertRule>; rule_labels: Record<string, string> }
export type AlertEventRow = { id: string; created_at: string; rule: string; rule_label: string; level: string; message: string; value: number | null
  threshold: number | null; sent: boolean; http_status: number | null; error: string }
export type AlertFinding = { rule: string; value: number | null; threshold: number | null; message: string }

export const fetchDataQuality = () => call<DataQuality>('/api/admin/data-quality')
export const fetchReports = (params: Record<string, string | number | undefined>) => call<Paged<ReportRow> & { counts: Record<string, number>; kinds: Record<string, string> }>(`/api/admin/reports${qs(params)}`)
export const acceptReport = (id: string, body: { edge_id?: number; kind?: string; expires_days?: number; note?: string }) =>
  call<{ report: ReportRow; override: OverrideRow }>(`/api/admin/reports/${id}/accept`, { method: 'POST', body: JSON.stringify(body) })
export const rejectReport = (id: string, note: string) => call<ReportRow>(`/api/admin/reports/${id}/reject`, { method: 'POST', body: JSON.stringify({ note }) })
export const fetchOverrides = (params: Record<string, string | number | boolean | undefined>) => call<Paged<OverrideRow>>(`/api/admin/overrides${qs(params)}`)
export const createOverride = (body: { edge_id: number; kind: string; expires_days?: number; note?: string }) => call<OverrideRow>('/api/admin/overrides', { method: 'POST', body: JSON.stringify(body) })
export const deactivateOverride = (id: string) => call<OverrideRow>(`/api/admin/overrides/${id}`, { method: 'DELETE' })
export const fetchAlertSettings = () => call<AlertSettings>('/api/admin/alerts/settings')
export const saveAlertSettings = (patch: Partial<Omit<AlertSettings, 'rules'>> & { rules?: Record<string, AlertRule> }) =>
  call<AlertSettings>('/api/admin/alerts/settings', { method: 'PUT', body: JSON.stringify(patch) })
export const testAlert = () => call<AlertEventRow>('/api/admin/alerts/test', { method: 'POST' })
export const evaluateAlerts = () => call<{ findings: AlertFinding[]; sent: AlertEventRow[]; enabled: boolean; webhook_configured: boolean }>('/api/admin/alerts/evaluate', { method: 'POST' })
export const fetchAlertEvents = (params: Record<string, string | number | undefined>) => call<Paged<AlertEventRow> & { rule_labels: Record<string, string> }>(`/api/admin/alerts/events${qs(params)}`)
