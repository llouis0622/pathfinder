import { formatDistance, formatMinutes, legColor, legTitle } from '../lib/format'
import type { Leg, Route } from '../types'

type Props = {
  route: Route
  originName: string
  destinationName: string
  onBack: () => void
  onChoose: () => void
  choosing?: boolean
  chosen?: boolean
}

function walkMeta(leg: Leg): string {
  const parts = [formatDistance(leg.distance_m)]
  if (leg.max_grade_pct !== null && leg.max_grade_pct >= 3) parts.push(`경사 ${leg.max_grade_pct.toFixed(0)}%`)
  if (leg.stairs_count > 0) parts.push(`계단 ${leg.stairs_count}곳`)
  if (leg.shade_ratio !== null && leg.shade_ratio > 0) parts.push(`그늘 ${Math.round(leg.shade_ratio * 100)}%`)
  return parts.join(' · ')
}

/** 네이버 길찾기식 세로 타임라인 */
export default function RouteDetail({ route, originName, destinationName, onBack, onChoose, choosing, chosen }: Props) {
  return (
    <section className="detail" aria-label="경로 상세">
      <button type="button" className="detail__back" onClick={onBack} aria-label="경로 목록으로">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
        <span>{Math.round(route.total_duration_min)}분 · 도보 {formatDistance(route.walk_distance_m)}</span>
      </button>
      <ol className="timeline">
        <li className="tl tl--point">
          <span className="tl__dot tl__dot--origin" />
          <div className="tl__body"><strong>{originName || '출발'}</strong></div>
        </li>
        {route.legs.map((leg, i) => {
          const color = legColor(leg)
          if (leg.kind === 'walk') {
            return (
              <li key={i} className="tl tl--walk">
                <span className="tl__line tl__line--dashed" />
                <div className="tl__body">
                  <span className="tl__title">도보 {formatMinutes(leg.duration_s)}</span>
                  <span className="tl__meta">{walkMeta(leg)}</span>
                </div>
              </li>
            )
          }
          if (leg.kind === 'vertical') {
            const warn = leg.verified === null
            return (
              <li key={i} className="tl tl--vertical">
                <span className="tl__line" />
                <div className="tl__body">
                  <span className={`tl__meta${warn ? ' is-warn' : ''}`}>
                    {leg.station_name ? `${leg.station_name} · ` : ''}{legTitle(leg)}
                  </span>
                </div>
              </li>
            )
          }
          return (
            <li key={i} className="tl tl--ride">
              <span className="tl__dot" style={{ background: color }} />
              <span className="tl__line tl__line--solid" style={{ background: color }} />
              <div className="tl__body">
                <strong>{leg.from_name}</strong>
                <span className="tl__title" style={{ color }}>
                  {legTitle(leg)} · {leg.stop_count}정거장 · {formatMinutes(leg.duration_s)}
                </span>
                <span className="tl__meta">
                  대기 약 {formatMinutes(leg.wait_s)}
                  {leg.mode === 'bus' && ` · 저상 ${leg.low_floor_ratio === null ? '미확인' : `${Math.round(leg.low_floor_ratio * 100)}%`}`}
                </span>
                <strong className="tl__to">{leg.to_name}</strong>
              </div>
            </li>
          )
        })}
        <li className="tl tl--point">
          <span className="tl__dot tl__dot--dest" />
          <div className="tl__body"><strong>{destinationName || '도착'}</strong></div>
        </li>
      </ol>
      <button type="button" className={`cta${chosen ? ' cta--done' : ''}`} onClick={onChoose} disabled={choosing || chosen}>
        {chosen ? '이 경로로 안내 중' : choosing ? '기록 중…' : '이 경로로 가기'}
      </button>
    </section>
  )
}
