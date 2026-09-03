import { formatDistance, formatMinutes, legColor, legTitle } from '../lib/format'
import type { Leg, Route } from '../types'
import type { ReportTarget } from './ReportDialog'

type Props = {
  route: Route
  originName: string
  destinationName: string
  onBack: () => void
  onChoose: () => void
  choosing?: boolean
  chosen?: boolean
  onSpeak?: () => void
  speaking?: boolean
  onShare?: () => void
  onReport?: (target: ReportTarget) => void
}

function walkMeta(leg: Leg): string {
  const parts = [formatDistance(leg.distance_m)]
  if (leg.max_grade_pct !== null && leg.max_grade_pct >= 3) parts.push(`경사 ${leg.max_grade_pct.toFixed(0)}%`)
  if (leg.stairs_count > 0) parts.push(`계단 ${leg.stairs_count}곳`)
  if (leg.shade_ratio !== null && leg.shade_ratio > 0) parts.push(`그늘 ${Math.round(leg.shade_ratio * 100)}%`)
  return parts.join(' · ')
}

function legPoint(leg: Leg): { lat: number; lng: number } | null {
  const p = leg.path
  if (!p.length) return null
  const mid = p[Math.floor(p.length / 2)]
  return { lat: mid[0], lng: mid[1] }
}

/** 네이버 길찾기식 세로 타임라인 */
export default function RouteDetail({ route, originName, destinationName, onBack, onChoose, choosing, chosen, onSpeak, speaking, onShare, onReport }: Props) {
  const report = (leg: Leg, kind: string) => {
    const pt = legPoint(leg) ?? (leg.kind === 'vertical' && route.path[0] ? { lat: route.path[0][0], lng: route.path[0][1] } : null)
    if (!pt || !onReport) return
    onReport({ ...pt, placeName: leg.kind === 'vertical' ? leg.station_name : leg.kind === 'ride' ? leg.from_name : '', defaultKind: kind })
  }
  return (
    <section className="detail" aria-label="경로 상세">
      <div className="detail__head">
        <button type="button" className="detail__back" onClick={onBack} aria-label="경로 목록으로">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
          <span>{Math.round(route.total_duration_min)}분 · 도보 {formatDistance(route.walk_distance_m)}</span>
        </button>
        <div className="detail__tools">
          {onSpeak && (
            <button type="button" className={`detail__tool${speaking ? ' is-on' : ''}`} onClick={onSpeak} aria-pressed={speaking} aria-label={speaking ? '읽기 멈춤' : '경로 읽어주기'}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 5L6 9H2v6h4l5 4V5z" /><path d="M15.5 8.5a5 5 0 010 7M19 5a9 9 0 010 14" /></svg>
              <span>{speaking ? '멈춤' : '읽기'}</span>
            </button>
          )}
          {onShare && (
            <button type="button" className="detail__tool" onClick={onShare} aria-label="경로 공유">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg>
              <span>공유</span>
            </button>
          )}
        </div>
      </div>
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
                  {onReport && <button type="button" className="tl__report" onClick={() => report(leg, leg.stairs_count > 0 ? 'ok' : 'stairs')}>문제 제보</button>}
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
                  {onReport && <button type="button" className="tl__report" onClick={() => report(leg, 'elevator_broken')}>{leg.facility === 'elevator' ? '고장 제보' : '문제 제보'}</button>}
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
