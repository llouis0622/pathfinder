import { formatDistance, formatMinutes, legIcon, legTitle, modeColor } from '../lib/format'
import type { Route } from '../types'

type Props = { route: Route }

export default function RouteDetail({ route }: Props) {
  return (
    <section className="detail" aria-label={`${route.rank}순위 경로 상세`}>
      <h3 className="section__title">구간 안내</h3>
      <ol className="legs">
        {route.legs.map((leg, i) => {
          const color = leg.kind === 'walk' ? modeColor('walk') : leg.kind === 'ride' ? modeColor(leg.mode) : '#7c3aed'
          return (
            <li key={i} className="leg" style={{ borderLeftColor: color }}>
              <span className="leg__icon" aria-hidden="true">{legIcon(leg)}</span>
              <div className="leg__body">
                <div className="leg__title">{legTitle(leg)}</div>
                <div className="leg__meta">
                  {leg.kind === 'walk' && (
                    <>
                      {leg.uphill_m > 1 && <span>오르막 {Math.round(leg.uphill_m)}m</span>}
                      {leg.downhill_m > 1 && <span>내리막 {Math.round(leg.downhill_m)}m</span>}
                      {leg.max_grade_pct !== null && <span>최대 경사 {leg.max_grade_pct.toFixed(0)}%</span>}
                      {leg.stairs_count > 0 && <span className="is-warn">계단 {leg.stairs_count}곳 · 약 {leg.step_count}단</span>}
                      {leg.shade_ratio !== null && <span>그늘 {Math.round(leg.shade_ratio * 100)}%</span>}
                      {leg.crossings > 0 && <span>횡단보도 {leg.crossings}곳</span>}
                    </>
                  )}
                  {leg.kind === 'ride' && (
                    <>
                      <span>{leg.from_name} → {leg.to_name}</span>
                      <span>대기·승차 약 {formatMinutes(leg.wait_s)}</span>
                      {leg.mode === 'bus' && (
                        <span className={leg.low_floor_ratio === null ? 'is-warn' : ''}>
                          저상버스 {leg.low_floor_ratio === null ? '미확인' : `${Math.round(leg.low_floor_ratio * 100)}%`}
                        </span>
                      )}
                      <span>{formatDistance(leg.distance_m)}</span>
                    </>
                  )}
                  {leg.kind === 'vertical' && (
                    <span className={leg.verified === null ? 'is-warn' : ''}>
                      {leg.verified === null ? '엘리베이터 여부를 현장에서 확인하세요' : leg.facility === 'elevator' ? '엘리베이터 이용 확인됨' : '엘리베이터 없음'} · {formatMinutes(leg.duration_s)}
                    </span>
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
