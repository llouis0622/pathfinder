import type { Badge, Leg, ProfileId, WeatherFlag } from '../types'

export const BADGE_LABELS: Record<Badge, string> = {
  fastest: '가장 빠른 길',
  shortest_walk: '도보가 가장 짧은 길',
  gentlest_slope: '경사가 가장 완만한 길',
  most_shade: '그늘이 가장 많은 길',
  fewest_transfers: '환승이 가장 적은 길',
  stair_free: '계단 없음',
  elevator_confirmed: '엘리베이터 확인됨',
}

export const BADGE_TONES: Record<Badge, 'primary' | 'good' | 'info'> = {
  fastest: 'primary',
  shortest_walk: 'primary',
  gentlest_slope: 'good',
  most_shade: 'good',
  fewest_transfers: 'info',
  stair_free: 'good',
  elevator_confirmed: 'good',
}

export const PROFILE_FALLBACK: { id: ProfileId; label: string; description: string }[] = [
  { id: 'wheelchair', label: '휠체어 이용자', description: '계단·급경사·좁은 보도를 피하고 엘리베이터와 저상버스만 이용' },
  { id: 'elderly', label: '고령자', description: '계단·급경사 부담을 줄이고 도보를 짧게, 더위·추위에 민감' },
  { id: 'walking_aid', label: '보행보조기·목발', description: '계단 부담을 더 크게 보고 엘리베이터를 우선' },
  { id: 'visually_impaired', label: '시각장애인', description: '신호 없는 횡단을 피하고 점자블록·난간이 있는 길을 우선' },
]

export const WEATHER_FLAG_LABELS: Record<WeatherFlag, string> = {
  heatwave: '폭염',
  heat: '더위',
  coldwave: '한파',
  cold: '추위',
  rain: '비·눈',
  bad_air: '미세먼지 나쁨',
  windy: '강풍',
}

export const MODE_COLORS: Record<string, string> = {
  walk: '#2563eb',
  subway: '#f06a00',
  bus: '#16a34a',
  transit: '#7c3aed',
}

export function modeColor(mode: string): string {
  return MODE_COLORS[mode] ?? MODE_COLORS.transit
}

export function gradeColor(grade: number | null): string {
  if (grade === null) return '#9ca3af'
  const g = Math.abs(grade)
  if (g < 3) return '#22c55e'
  if (g < 6) return '#eab308'
  if (g < 10) return '#f97316'
  return '#dc2626'
}

export function shadeColor(ratio: number): string {
  // 0 = 볕(주황) → 1 = 그늘(짙은 파랑)
  const r = Math.max(0, Math.min(1, ratio))
  const start = [249, 115, 22]
  const end = [30, 58, 138]
  const c = start.map((s, i) => Math.round(s + (end[i] - s) * r))
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`
}

export function formatMinutes(seconds: number): string {
  const min = Math.round(seconds / 60)
  if (min < 60) return `${Math.max(1, min)}분`
  return `${Math.floor(min / 60)}시간 ${min % 60}분`
}

export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.round(m)}m`
}

export function formatPercent(ratio: number | null): string {
  return ratio === null ? '정보 없음' : `${Math.round(ratio * 100)}%`
}

export function legTitle(leg: Leg): string {
  if (leg.kind === 'walk') return `도보 ${formatDistance(leg.distance_m)} · ${formatMinutes(leg.duration_s)}`
  if (leg.kind === 'ride') {
    const mode = leg.mode === 'subway' ? '지하철' : leg.mode === 'bus' ? '버스' : leg.mode
    return `${mode} ${leg.route_name || leg.route_id} · ${leg.stop_count}정거장 · ${formatMinutes(leg.duration_s)}`
  }
  const facility: Record<Leg['facility'], string> = {
    '': '수직 이동',
    elevator: '엘리베이터',
    escalator: '에스컬레이터',
    stairs: '계단',
    unknown: '엘리베이터 확인 필요',
  }
  return `${facility[leg.facility]}${leg.station_name ? ` · ${leg.station_name}` : ''}`
}

export function legIcon(leg: Leg): string {
  if (leg.kind === 'walk') return '🚶'
  if (leg.kind === 'ride') return leg.mode === 'subway' ? '🚇' : '🚌'
  if (leg.facility === 'elevator') return '🛗'
  if (leg.facility === 'stairs') return '🪜'
  if (leg.facility === 'escalator') return '↗'
  return '❓'
}

export function toLocalDatetimeInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function localInputToIso(value: string): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  const offset = -d.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0')
  return `${value}:00${sign}${pad(offset / 60)}:${pad(offset % 60)}`
}
