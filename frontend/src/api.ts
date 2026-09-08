import type { ProfileId, ShadeResponse, AuthProviders, ChooseResponse, Place, Preferences, Profile, Route, RouteSearchRequest, RouteSearchResponse, User, Weather } from './types'

// VITE_BACKEND_URL 이 비어 있으면 같은 오리진의 /api 를 쓴다 (vite proxy / nginx).
const base = (import.meta.env.VITE_BACKEND_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, { headers: { 'content-type': 'application/json' }, credentials: 'include', ...init })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (body.detail) detail = JSON.stringify(body.detail)
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export function searchPlaces(query: string, near?: { lat: number; lng: number }): Promise<{ places: Place[]; source: string }> {
  const params = new URLSearchParams({ query })
  if (near) {
    params.set('lat', String(near.lat))
    params.set('lng', String(near.lng))
  }
  return request(`/api/place/search?${params.toString()}`)
}

export function fetchProfiles(): Promise<Profile[]> {
  return request('/api/profiles')
}

export function fetchWeather(lat: number, lng: number, at?: string | null): Promise<Weather> {
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng) })
  if (at) params.set('at', at)
  return request(`/api/weather?${params.toString()}`)
}

export function searchRoutes(payload: RouteSearchRequest): Promise<RouteSearchResponse> {
  return request('/api/route', { method: 'POST', body: JSON.stringify(payload) })
}

export type StoredRoute = { request_id: string; routes: Route[]; status: string; profile: ProfileId; origin: { lat: number; lng: number; name: string }; destination: { lat: number; lng: number; name: string }; created_at: string; weather: Weather | null; metadata: RouteSearchResponse['metadata'] | null }
export function fetchStoredRoute(requestId: string): Promise<StoredRoute> {
  return request(`/api/route/${encodeURIComponent(requestId)}`)
}

export function chooseRoute(requestId: string, routeId: string): Promise<ChooseResponse> {
  return request(`/api/route/${encodeURIComponent(requestId)}/choose`, { method: 'POST', body: JSON.stringify({ route_id: routeId }) })
}

// ---------- 로그인 ----------
export function fetchAuthProviders(): Promise<AuthProviders> {
  return request('/api/auth/providers')
}

export async function fetchMe(): Promise<User | null> {
  const res = await request<{ user: User | null }>('/api/auth/me')
  return res.user
}

export function loginUrl(provider: 'kakao' | 'naver'): string {
  return `${base}/api/auth/${provider}/login`
}

export function devLogin(nickname = '데모 사용자'): Promise<User> {
  return request(`/api/auth/dev/login?${new URLSearchParams({ nickname }).toString()}`, { method: 'POST' })
}

export function logout(): Promise<{ ok: boolean }> {
  return request('/api/auth/logout', { method: 'POST' })
}

export function fetchPreferences(): Promise<Preferences> {
  return request('/api/me/preferences')
}

export function resetPreferences(): Promise<{ ok: boolean }> {
  return request('/api/me/preferences', { method: 'DELETE' })
}

/** 화면 범위의 보행 엣지 그늘 비율 (엣지 id → 0~1). 범위가 넓으면 422. */
export async function fetchShade(bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number; at?: string }, signal?: AbortSignal): Promise<ShadeResponse> {
  const p = new URLSearchParams()
  Object.entries(bbox).forEach(([k, v]) => { if (v !== undefined) p.set(k, String(v)) })
  const res = await fetch(`${base}/api/shade?${p.toString()}`, { credentials: 'include', signal })
  if (!res.ok) {
    let detail = `그늘을 불러오지 못했어요 (${res.status})`
    try { const body = await res.json(); if (typeof body?.detail === 'string') detail = body.detail } catch { /* 본문 없음 */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<ShadeResponse>
}

// ---------------------------------------------------------------- 즐겨찾기·최근 (로그인)
export type MyPlace = { id: string; label: string; name: string; address: string; lat: number; lng: number; sort: number }
export const fetchMyPlaces = () => request<MyPlace[]>('/api/me/places')
export const addMyPlace = (p: { label: string; name: string; address: string; lat: number; lng: number }) => request<MyPlace>('/api/me/places', { method: 'POST', body: JSON.stringify(p) })
export const deleteMyPlace = (id: string) => request<{ ok: boolean }>(`/api/me/places/${id}`, { method: 'DELETE' })
export const fetchRecent = () => request<{ origin: { name: string; lat: number; lng: number }; destination: { name: string; lat: number; lng: number }; profile: string; at: string }[]>('/api/me/recent')

// ---------------------------------------------------------------- 시설 제보
export const fetchReportKinds = () => request<{ kind: string; label: string }[]>('/api/reports/kinds')
export const createReport = (body: { lat: number; lng: number; kind: string; note?: string; place_name?: string; request_id?: string }) =>
  request<{ id: string; status: string; kind: string; kind_label: string; created_at: string }>('/api/reports', { method: 'POST', body: JSON.stringify(body) })
