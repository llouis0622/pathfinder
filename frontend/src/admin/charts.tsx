/**
 * 관리자용 경량 SVG 차트. 외부 라이브러리 없이 선·막대·비율·발산 막대와 호버 툴팁을 제공한다.
 * 색은 역할별 슬롯(계열 1~4)만 쓰고, 텍스트는 항상 회색 토큰을 쓴다. 모든 차트는 "표로 보기" 를 함께 낸다.
 */
import { useId, useMemo, useState, type ReactNode } from 'react'

export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'] as const
export const POSITIVE = '#2a78d6'
export const NEGATIVE = '#eb6834'
export const NEUTRAL = '#d1d6db'

export type Series = { key: string; label: string; values: (number | null)[]; color?: string }

const nf = new Intl.NumberFormat('ko-KR')
export const fmtNum = (v: number | null | undefined, digits = 0) => (v === null || v === undefined ? '–' : nf.format(Number(v.toFixed(digits))))
export const fmtPct = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? '–' : `${(v * 100).toFixed(digits)}%`)
export const fmtMs = (v: number | null | undefined) => (v === null || v === undefined ? '–' : v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`)

function niceMax(v: number): number {
  if (v <= 0) return 1
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const m = v / p
  const step = m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10
  return step * p
}

function DataTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="chart__table">
      <summary>표로 보기</summary>
      <div className="adm-scroll">
        <table className="adm-table adm-table--compact">
          <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </details>
  )
}

function Legend({ series }: { series: { label: string; color: string }[] }) {
  if (series.length < 2) return null
  return (
    <div className="chart__legend">
      {series.map((s) => <span key={s.label} className="chart__legend-item"><i style={{ background: s.color }} />{s.label}</span>)}
    </div>
  )
}

// ---------------------------------------------------------------- 선 차트 (시계열)
export function LineChart({ labels, series, height = 220, format = (v: number) => fmtNum(v), title }: {
  labels: string[]; series: Series[]; height?: number; format?: (v: number) => string; title?: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const id = useId()
  const W = 720
  const padL = 44, padR = 12, padT = 12, padB = 28
  const innerW = W - padL - padR, innerH = height - padT - padB
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values.map((v) => v ?? 0))))
  const n = labels.length
  const x = (i: number) => padL + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
  const y = (v: number) => padT + innerH - (v / max) * innerH
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max)
  const colored = series.map((s, i) => ({ ...s, color: s.color ?? SERIES[i % SERIES.length] }))
  const labelEvery = Math.max(1, Math.ceil(n / 8))

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const i = Math.round(((px - padL) / innerW) * (n - 1))
    setHover(Math.min(n - 1, Math.max(0, i)))
  }
  const tipLeft = hover !== null ? (x(hover) / W) * 100 : 0

  return (
    <div className="chart">
      {title && <div className="chart__title">{title}</div>}
      <Legend series={colored} />
      <div className="chart__plot">
        <svg viewBox={`0 0 ${W} ${height}`} className="chart__svg" role="img" aria-label={title ?? '선 차트'} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="chart__grid" />
              <text x={padL - 8} y={y(t) + 4} className="chart__tick" textAnchor="end">{format(t)}</text>
            </g>
          ))}
          {labels.map((l, i) => (i % labelEvery === 0 || i === n - 1) && (
            <text key={l + i} x={x(i)} y={height - 8} className="chart__tick" textAnchor="middle">{l}</text>
          ))}
          {colored.map((s) => {
            const pts = s.values.map((v, i) => (v === null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`))
            const d = pts.filter(Boolean).join(' ')
            return (
              <g key={s.key}>
                <polyline points={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                {s.values.map((v, i) => (v !== null && (s.values[i - 1] ?? null) === null && (s.values[i + 1] ?? null) === null) && (
                  <circle key={i} cx={x(i)} cy={y(v)} r={4} fill={s.color} />
                ))}
                {hover !== null && s.values[hover] !== null && (
                  <circle cx={x(hover)} cy={y(s.values[hover] as number)} r={5} fill={s.color} stroke="#fff" strokeWidth={2} />
                )}
              </g>
            )
          })}
          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={padT} y2={padT + innerH} className="chart__crosshair" />}
          <clipPath id={id}><rect x={padL} y={padT} width={innerW} height={innerH} /></clipPath>
        </svg>
        {hover !== null && (
          <div className="chart__tip" style={{ left: `${tipLeft}%` }}>
            <div className="chart__tip-title">{labels[hover]}</div>
            {colored.map((s) => (
              <div key={s.key} className="chart__tip-row"><i style={{ background: s.color }} />{s.label}<b>{s.values[hover] === null ? '–' : format(s.values[hover] as number)}</b></div>
            ))}
          </div>
        )}
      </div>
      <DataTable head={['구간', ...colored.map((s) => s.label)]} rows={labels.map((l, i) => [l, ...colored.map((s) => (s.values[i] === null ? '–' : format(s.values[i] as number)))])} />
    </div>
  )
}

// ---------------------------------------------------------------- 세로 막대 (분포)
export function BarChart({ labels, values, height = 200, color = SERIES[0], format = (v: number) => fmtNum(v), title, highlight }: {
  labels: string[]; values: number[]; height?: number; color?: string; format?: (v: number) => string; title?: string; highlight?: (i: number) => boolean
}) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 720
  const padL = 40, padR = 8, padT = 10, padB = 26
  const innerW = W - padL - padR, innerH = height - padT - padB
  const n = Math.max(1, values.length)
  const max = niceMax(Math.max(1, ...values))
  const slot = innerW / n
  const bw = Math.max(4, Math.min(28, slot - 2))
  const y = (v: number) => padT + innerH - (v / max) * innerH
  const labelEvery = Math.max(1, Math.ceil(n / 12))
  return (
    <div className="chart">
      {title && <div className="chart__title">{title}</div>}
      <div className="chart__plot">
        <svg viewBox={`0 0 ${W} ${height}`} className="chart__svg" role="img" aria-label={title ?? '막대 차트'} onMouseLeave={() => setHover(null)}>
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line x1={padL} x2={W - padR} y1={y(t * max)} y2={y(t * max)} className="chart__grid" />
              <text x={padL - 6} y={y(t * max) + 4} className="chart__tick" textAnchor="end">{format(t * max)}</text>
            </g>
          ))}
          {values.map((v, i) => {
            const cx = padL + slot * i + slot / 2
            const h = Math.max(0, padT + innerH - y(v))
            const on = hover === i
            return (
              <g key={i} onMouseEnter={() => setHover(i)}>
                <rect x={padL + slot * i} y={padT} width={slot} height={innerH} fill="transparent" />
                <rect x={cx - bw / 2} y={y(v)} width={bw} height={h} rx={3} fill={highlight?.(i) ? NEGATIVE : color} opacity={hover === null || on ? 1 : 0.55} />
                {(i % labelEvery === 0 || i === n - 1) && <text x={cx} y={height - 8} className="chart__tick" textAnchor="middle">{labels[i]}</text>}
              </g>
            )
          })}
        </svg>
        {hover !== null && (
          <div className="chart__tip" style={{ left: `${((padL + slot * hover + slot / 2) / W) * 100}%` }}>
            <div className="chart__tip-title">{labels[hover]}</div>
            <div className="chart__tip-row"><b>{format(values[hover])}</b></div>
          </div>
        )}
      </div>
      <DataTable head={['구간', '값']} rows={labels.map((l, i) => [l, format(values[i])])} />
    </div>
  )
}

// ---------------------------------------------------------------- 가로 순위 막대 (상위 N)
export function RankBars({ items, format = (v: number) => fmtNum(v), color = SERIES[0], max: maxIn, title, empty = '데이터 없음', render }: {
  items: { label: string; value: number; sub?: string; href?: string }[]; format?: (v: number) => string; color?: string; max?: number; title?: string
  empty?: string; render?: (label: string) => ReactNode
}) {
  const max = maxIn ?? Math.max(1, ...items.map((i) => i.value))
  return (
    <div className="chart">
      {title && <div className="chart__title">{title}</div>}
      {items.length === 0 && <div className="adm-empty">{empty}</div>}
      <ul className="rank">
        {items.map((it, i) => (
          <li key={it.label + i} className="rank__row">
            <span className="rank__label" title={it.label}>{render ? render(it.label) : it.label}{it.sub && <small>{it.sub}</small>}</span>
            <span className="rank__bar"><i style={{ width: `${Math.max(1.5, (it.value / max) * 100)}%`, background: color }} /></span>
            <span className="rank__value">{format(it.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------- 비율 (100% 누적) 막대
export function ShareBar({ items, title, format = (v: number) => fmtNum(v) }: {
  items: { label: string; value: number; color?: string }[]; title?: string; format?: (v: number) => string
}) {
  const total = items.reduce((a, b) => a + b.value, 0)
  const colored = items.map((it, i) => ({ ...it, color: it.color ?? SERIES[i % SERIES.length] }))
  return (
    <div className="chart">
      {title && <div className="chart__title">{title}</div>}
      <div className="share" role="img" aria-label={title ?? '비율'}>
        {total === 0 && <i className="share__seg" style={{ width: '100%', background: NEUTRAL }} />}
        {total > 0 && colored.map((it) => it.value > 0 && (
          <i key={it.label} className="share__seg" style={{ width: `${(it.value / total) * 100}%`, background: it.color }} title={`${it.label} ${format(it.value)}`} />
        ))}
      </div>
      <ul className="share__legend">
        {colored.map((it) => (
          <li key={it.label}><i style={{ background: it.color }} />{it.label}<b>{format(it.value)}</b><span>{total ? `${((it.value / total) * 100).toFixed(0)}%` : '–'}</span></li>
        ))}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------- 발산 막대 (가중치: 0 중심)
export function DivergingBars({ items, title, max: maxIn, format = (v: number) => v.toFixed(2) }: {
  items: { key: string; label: string; value: number; negativeLabel?: string; positiveLabel?: string; sub?: string }[]
  title?: string; max?: number; format?: (v: number) => string
}) {
  const max = maxIn ?? Math.max(0.5, ...items.map((i) => Math.abs(i.value)))
  return (
    <div className="chart">
      {title && <div className="chart__title">{title}</div>}
      <ul className="div">
        {items.map((it) => {
          const w = Math.min(100, (Math.abs(it.value) / max) * 100)
          return (
            <li key={it.key} className="div__row">
              <span className="div__neg">{it.negativeLabel ?? ''}</span>
              <span className="div__track">
                <i className="div__zero" />
                {it.value < 0 && <i className="div__bar div__bar--neg" style={{ width: `${w / 2}%`, background: NEGATIVE }} />}
                {it.value > 0 && <i className="div__bar div__bar--pos" style={{ width: `${w / 2}%`, background: POSITIVE }} />}
                <b className={`div__value${it.value < 0 ? ' is-neg' : it.value > 0 ? ' is-pos' : ''}`}>{format(it.value)}</b>
              </span>
              <span className="div__pos">{it.positiveLabel ?? ''}{it.sub && <small>{it.sub}</small>}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------- KPI 타일
export function StatTile({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'warn' | 'good' }) {
  return (
    <div className={`tile${tone ? ` tile--${tone}` : ''}`}>
      <div className="tile__label">{label}</div>
      <div className="tile__value">{value}</div>
      {sub && <div className="tile__sub">{sub}</div>}
    </div>
  )
}

/** 시계열 배열에서 라벨(MM/DD)만 뽑는다. */
export function shortDates(dates: string[]): string[] {
  return dates.map((d) => d.slice(5).replace('-', '/'))
}

export function useSeries<T>(rows: T[], pick: (r: T) => number | null): (number | null)[] {
  return useMemo(() => rows.map(pick), [rows, pick])
}
