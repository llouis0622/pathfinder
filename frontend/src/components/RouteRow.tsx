import { BADGE_LABELS, formatDistance, formatDuration, legColor, routeSummary } from '../lib/format'
import type { Route } from '../types'

type Props = {
  route: Route
  selected: boolean
  onSelect: () => void
}

/** 네이버·카카오 길찾기 스타일의 경로 행: 소요시간 · 수단 바 · 요약 · 태그 */
export default function RouteRow({ route, selected, onSelect }: Props) {
  const duration = formatDuration(route.total_duration_min)
  const bars = route.legs.filter((l) => l.kind !== 'vertical')
  const total = bars.reduce((s, l) => s + l.duration_s + (l.kind === 'ride' ? 0 : 0), 0) || 1
  const tags = route.badges.slice(0, 3).map((b) => BADGE_LABELS[b])
  const caution = route.cautions[0]

  return (
    <article className={`row${selected ? ' is-selected' : ''}`} role="option" aria-selected={selected} tabIndex={0}
      onClick={onSelect} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}>
      <div className="row__top">
        <div className="row__time">
          <strong>{duration.value}</strong><span>{duration.unit}</span>
        </div>
        <div className="row__right">
          {route.rank === 1 && <span className="row__recommend">추천</span>}
          <span className="row__walk">도보 {formatDistance(route.walk_distance_m)}</span>
        </div>
      </div>
      <div className="bar" aria-hidden="true">
        {bars.map((leg, i) => (
          <span key={i} className={`bar__seg bar__seg--${leg.kind}`}
            style={{ flexGrow: Math.max(leg.duration_s, total * 0.06), background: legColor(leg, leg.kind !== 'walk') }}>
            {leg.kind === 'ride' && <em>{leg.route_name || leg.route_id}</em>}
          </span>
        ))}
      </div>
      <p className="row__summary">{routeSummary(route.legs)}</p>
      {(tags.length > 0 || route.transfers > 0) && (
        <ul className="tags">
          {route.transfers > 0 && <li className="tag">환승 {route.transfers}회</li>}
          {tags.map((t) => <li key={t} className="tag">{t}</li>)}
        </ul>
      )}
      {caution && <p className="row__caution">{caution}</p>}
    </article>
  )
}
