import { BADGE_LABELS, BADGE_TONES, formatDistance, formatPercent } from '../lib/format'
import type { Route } from '../types'

type Props = {
  route: Route
  selected: boolean
  onSelect: () => void
  shadeAvailable: boolean
}

export default function RouteCard({ route, selected, onSelect, shadeAvailable }: Props) {
  const f = route.features
  return (
    <article className={`card${selected ? ' is-selected' : ''}`} aria-selected={selected} role="option" tabIndex={0}
      onClick={onSelect} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}>
      <header className="card__head">
        <span className="card__rank">{route.rank}순위</span>
        <span className="card__time">{route.total_duration_min}분</span>
      </header>
      <p className="card__summary">{route.summary}</p>
      {route.badges.length > 0 && (
        <ul className="badges" aria-label="경로 특성">
          {route.badges.map((b) => (
            <li key={b} className={`badge badge--${BADGE_TONES[b]}`}>{BADGE_LABELS[b]}</li>
          ))}
        </ul>
      )}
      <dl className="metrics">
        <div><dt>도보</dt><dd>{formatDistance(route.walk_distance_m)}</dd></div>
        <div><dt>환승</dt><dd>{route.transfers}회</dd></div>
        <div><dt>최대 경사</dt><dd>{f.max_grade_pct === null ? '정보 없음' : `${f.max_grade_pct.toFixed(0)}%`}</dd></div>
        <div><dt>그늘</dt><dd>{shadeAvailable ? formatPercent(f.shade_ratio) : '—'}</dd></div>
        <div><dt>계단</dt><dd>{f.stairs_count === 0 ? '없음' : `${f.stairs_count}곳`}</dd></div>
        <div><dt>엘리베이터</dt><dd>{f.elevator_count > 0 ? `${f.elevator_count}회` : f.unverified_vertical_count > 0 ? '확인 필요' : '—'}</dd></div>
      </dl>
      {route.cautions.length > 0 && (
        <ul className="cautions" aria-label="주의사항">
          {route.cautions.map((c) => <li key={c}>⚠ {c}</li>)}
        </ul>
      )}
    </article>
  )
}
