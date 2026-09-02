import { useMemo } from 'react'
import { gradeColor, modeColor, shadeColor } from '../lib/format'
import type { MapOverlay, Place, Route } from '../types'

type Props = {
  origin: Place | null
  destination: Place | null
  routes: Route[]
  selectedId: string | null
  overlay: MapOverlay
  onSelect: (id: string) => void
}

const W = 800
const H = 520
const PAD = 40

/** Kakao 키가 없을 때 쓰는 SVG 약식 지도. 경로 좌표를 뷰박스에 정규화해 그린다. */
export default function SchematicMap({ origin, destination, routes, selectedId, overlay, onSelect }: Props) {
  const project = useMemo(() => {
    const pts: number[][] = []
    routes.forEach((r) => pts.push(...r.path))
    if (origin) pts.push([origin.lat, origin.lng])
    if (destination) pts.push([destination.lat, destination.lng])
    if (pts.length === 0) return null
    const lats = pts.map((p) => p[0])
    const lngs = pts.map((p) => p[1])
    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLng = Math.min(...lngs)
    const maxLng = Math.max(...lngs)
    const cos = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180))
    const spanX = Math.max((maxLng - minLng) * cos, 1e-5)
    const spanY = Math.max(maxLat - minLat, 1e-5)
    const scale = Math.min((W - 2 * PAD) / spanX, (H - 2 * PAD) / spanY)
    return ([lat, lng]: number[]) => ({
      x: PAD + (lng - minLng) * cos * scale + ((W - 2 * PAD) - spanX * scale) / 2,
      y: H - PAD - (lat - minLat) * scale - ((H - 2 * PAD) - spanY * scale) / 2,
    })
  }, [routes, origin, destination])

  if (!project) {
    return (
      <div className="schematic schematic--empty">
        <p>출발지와 도착지를 고르고 길찾기를 누르면 경로가 여기에 그려집니다.</p>
      </div>
    )
  }
  const toPoints = (path: number[][]) => path.map((p) => { const q = project(p); return `${q.x.toFixed(1)},${q.y.toFixed(1)}` }).join(' ')
  const selected = routes.find((r) => r.id === selectedId) ?? routes[0]

  return (
    <svg className="schematic" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="약식 경로 지도">
      <rect width={W} height={H} fill="#eef2f7" />
      {routes.filter((r) => r !== selected).map((r) => (
        <polyline key={r.id} points={toPoints(r.path)} fill="none" stroke="#9ca3af" strokeWidth={4} strokeOpacity={0.7}
          style={{ cursor: 'pointer' }} onClick={() => onSelect(r.id)} />
      ))}
      {selected && selected.legs.map((leg, i) => {
        if (leg.kind === 'walk' && overlay !== 'mode') {
          return leg.segments.map((seg, j) => (
            <polyline key={`${i}-${j}`} points={toPoints(seg.path)} fill="none" strokeWidth={7} strokeLinecap="round"
              stroke={overlay === 'grade' ? gradeColor(seg.grade_pct) : shadeColor(seg.shade_ratio)} />
          ))
        }
        if (leg.path.length < 2) return null
        return (
          <polyline key={i} points={toPoints(leg.path)} fill="none" strokeWidth={leg.kind === 'ride' ? 8 : 6} strokeLinecap="round"
            stroke={modeColor(leg.kind === 'walk' ? 'walk' : leg.mode)} strokeDasharray={leg.kind === 'ride' ? '14 8' : undefined} />
        )
      })}
      {selected && selected.legs.filter((l) => l.kind === 'vertical' && l.path[0]).map((leg, i) => {
        const p = project(leg.path[0])
        return <text key={`v${i}`} x={p.x} y={p.y + 6} fontSize={18} textAnchor="middle">{leg.facility === 'elevator' ? '🛗' : leg.facility === 'unknown' ? '❓' : '🪜'}</text>
      })}
      {origin && (() => { const p = project([origin.lat, origin.lng]); return <g><circle cx={p.x} cy={p.y} r={9} fill="#1d4ed8" stroke="#fff" strokeWidth={3} /><text x={p.x} y={p.y - 14} fontSize={13} fontWeight={700} textAnchor="middle" fill="#1d4ed8">출발</text></g> })()}
      {destination && (() => { const p = project([destination.lat, destination.lng]); return <g><circle cx={p.x} cy={p.y} r={9} fill="#dc2626" stroke="#fff" strokeWidth={3} /><text x={p.x} y={p.y - 14} fontSize={13} fontWeight={700} textAnchor="middle" fill="#dc2626">도착</text></g> })()}
    </svg>
  )
}
