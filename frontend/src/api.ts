import type { Place, Profile, Route, RouteSearchRequest, RouteSearchResponse, Weather } from './types'

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
  const res = await fetch(`${base}${path}`, { headers: { 'content-type': 'application/json' }, ...init })
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

export function fetchStoredRoute(requestId: string): Promise<{ routes: Route[]; status: string }> {
  return request(`/api/route/${encodeURIComponent(requestId)}`)
}
