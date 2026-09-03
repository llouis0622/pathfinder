/** 게스트용 즐겨찾기·최근 검색 (브라우저 저장). 로그인 사용자는 서버(/api/me/places, /api/me/recent)를 쓴다. */
import type { Place } from '../types'

export type Favorite = { id: string; label: string; name: string; address: string; lat: number; lng: number }
export type Recent = { origin: Pick<Place, 'name' | 'lat' | 'lng'>; destination: Pick<Place, 'name' | 'lat' | 'lng'>; profile: string; at: string }

const FAV_KEY = 'pf.favorites'
const RECENT_KEY = 'pf.recent'
const ONBOARD_KEY = 'pf.onboarded'
const MAX_RECENT = 8

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* 저장 불가 */ }
}

export const localFavorites = {
  list: (): Favorite[] => read<Favorite[]>(FAV_KEY, []),
  save(label: string, place: Place): Favorite[] {
    const list = localFavorites.list().filter((f) => f.label !== label)
    list.push({ id: `local-${Date.now()}`, label, name: place.name, address: place.address, lat: place.lat, lng: place.lng })
    write(FAV_KEY, list.slice(-20))
    return localFavorites.list()
  },
  remove(id: string): Favorite[] {
    write(FAV_KEY, localFavorites.list().filter((f) => f.id !== id))
    return localFavorites.list()
  },
}

export const localRecent = {
  list: (): Recent[] => read<Recent[]>(RECENT_KEY, []),
  push(origin: Place, destination: Place, profile: string): Recent[] {
    const key = (r: Recent) => `${r.origin.lat.toFixed(4)},${r.origin.lng.toFixed(4)}>${r.destination.lat.toFixed(4)},${r.destination.lng.toFixed(4)}`
    const entry: Recent = { origin: { name: origin.name, lat: origin.lat, lng: origin.lng }, destination: { name: destination.name, lat: destination.lat, lng: destination.lng }, profile, at: new Date().toISOString() }
    const list = [entry, ...localRecent.list().filter((r) => key(r) !== key(entry))].slice(0, MAX_RECENT)
    write(RECENT_KEY, list)
    return list
  },
  clear(): void { write(RECENT_KEY, []) },
}

export const onboarding = {
  seen: (): boolean => read<boolean>(ONBOARD_KEY, false),
  dismiss: (): void => write(ONBOARD_KEY, true),
}

export function toPlace(p: { name: string; lat: number; lng: number; address?: string }, id = 'saved'): Place {
  return { id, name: p.name, address: p.address ?? '', lat: p.lat, lng: p.lng, category: '', source: 'saved' }
}
