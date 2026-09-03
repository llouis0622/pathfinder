import type { Badge, Leg, ProfileId, Weather, WeatherFlag } from '../types'

// 짧은 태그 라벨 (네이버·카카오 길찾기 톤)
export const BADGE_LABELS: Record<Badge, string> = {
  fastest: '빠름',
  shortest_walk: '도보 적음',
  gentlest_slope: '경사 완만',
  most_shade: '그늘 많음',
  fewest_transfers: '환승 적음',
  stair_free: '계단 없음',
  elevator_confirmed: '엘리베이터',
}

export const PROFILE_FALLBACK: { id: ProfileId; label: string }[] = [
  { id: 'wheelchair', label: '휠체어' },
  { id: 'elderly', label: '고령자' },
  { id: 'walking_aid', label: '보행보조' },
  { id: 'visually_impaired', label: '시각장애' },
]

export const PROFILE_SHORT: Record<ProfileId, string> = {
  wheelchair: '휠체어',
  elderly: '고령자',
  walking_aid: '보행보조',
  visually_impaired: '시각장애',
}

export const WEATHER_FLAG_LABELS: Record<WeatherFlag, string> = {
  heatwave: '폭염',
  heat: '더위',
  coldwave: '한파',
  cold: '추위',
  rain: '비·눈',
  bad_air: '미세먼지',
  windy: '강풍',
}

// 부산 도시철도 공식 노선색. 그 외 수단은 그레이 톤.
const SUBWAY_LINE_COLORS: Record<string, string> = {
  '1호선': '#F06A00',
  '2호선': '#81BF48',
  '3호선': '#BB8C00',
  '4호선': '#217DCB',
  동해선: '#0054A6',
  부산김해경전철: '#8652A1',
}
export const WALK_COLOR = '#b0b8c1'
export const BUS_COLOR = '#4e5968'
export const SELECTED_WALK_COLOR = '#191f28'

export function legColor(leg: Pick<Leg, 'kind' | 'mode' | 'route_name'>, selected = true): string {
  if (leg.kind === 'walk') return selected ? SELECTED_WALK_COLOR : WALK_COLOR
  if (leg.kind === 'ride') {
    if (leg.mode === 'subway') return SUBWAY_LINE_COLORS[leg.route_name] ?? '#4e5968'
    return BUS_COLOR
  }
  return '#8b95a1'
}

export function gradeColor(grade: number | null): string {
  if (grade === null) return '#b0b8c1'
  const g = Math.abs(grade)
  if (g < 3) return '#191f28'
  if (g < 6) return '#6b7684'
  if (g < 10) return '#f59e0b'
  return '#e5484d'
}

export function shadeColor(ratio: number): string {
  // 0 = 볕(연한 회색) → 1 = 그늘(검정)
  const r = Math.max(0, Math.min(1, ratio))
  const start = [213, 218, 224]
  const end = [25, 31, 40]
  const c = start.map((s, i) => Math.round(s + (end[i] - s) * r))
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`
}

export function formatMinutes(seconds: number): string {
  const min = Math.round(seconds / 60)
  if (min < 60) return `${Math.max(1, min)}분`
  return `${Math.floor(min / 60)}시간 ${min % 60}분`
}

export function formatDuration(totalMin: number): { value: string; unit: string } {
  const min = Math.round(totalMin)
  if (min < 60) return { value: String(Math.max(1, min)), unit: '분' }
  return { value: `${Math.floor(min / 60)}시간 ${min % 60}`, unit: '분' }
}

export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.round(m)}m`
}

export function legTitle(leg: Leg): string {
  if (leg.kind === 'walk') return `도보 ${formatMinutes(leg.duration_s)}`
  if (leg.kind === 'ride') {
    const mode = leg.mode === 'subway' ? '' : leg.mode === 'bus' ? '버스 ' : ''
    return `${mode}${leg.route_name || leg.route_id}`
  }
  const facility: Record<Leg['facility'], string> = {
    '': '수직 이동',
    elevator: '엘리베이터',
    escalator: '에스컬레이터',
    stairs: '계단',
    unknown: '엘리베이터 확인 필요',
  }
  return facility[leg.facility]
}

/** 카드 요약 한 줄: "도보 6분 · 1호선 3정거장 · 도보 5분" (수직 이동은 생략) */
export function routeSummary(legs: Leg[]): string {
  return legs
    .filter((l) => l.kind !== 'vertical')
    .map((l) => (l.kind === 'walk' ? `도보 ${formatMinutes(l.duration_s)}` : `${legTitle(l)} ${l.stop_count}정거장`))
    .join(' · ')
}

export function weatherLine(w: Weather): string | null {
  if (w.source === 'none' || w.source === 'unavailable') return null
  const temp = w.feels_like_c ?? w.temp_c
  const sky: Record<string, string> = { clear: '맑음', cloudy: '흐림', rain: '비', snow: '눈', unknown: '' }
  const parts = [temp !== null && temp !== undefined ? `${Math.round(temp)}°` : '', sky[w.sky] ?? '']
  const flags = w.flags.filter((f) => !(f === 'heat' && w.flags.includes('heatwave')) && !(f === 'cold' && w.flags.includes('coldwave')))
  parts.push(...flags.map((f) => WEATHER_FLAG_LABELS[f] ?? f))
  return parts.filter(Boolean).join(' · ') || null
}

export function toLocalDatetimeInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
