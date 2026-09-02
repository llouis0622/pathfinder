import { useEffect, useMemo, useRef, useState } from 'react'
import { WALK_COLOR, gradeColor, legColor, shadeColor } from '../lib/format'
import type { MapInset, MapOverlay, Place, Route } from '../types'

type Props = {
  origin: Place | null
  destination: Place | null
  routes: Route[]
  selectedId: string | null
  overlay: MapOverlay
  inset?: MapInset
  onSelect: (id: string) => void
}

const DEFAULT_W = 800
const DEFAULT_H = 520
const PAD = 56
const NO_INSET: MapInset = { top: 0, right: 0, bottom: 0, left: 0 }

/** 컨테이너 픽셀 크기를 따라가 viewBox 를 1:1 로 맞춘다 (letterbox 없이 화면 전체가 지도). */
function useContainerSize(ref: React.RefObject<HTMLDivElement>): [number, number] {
  const [size, setSize] = useState<[number, number]>([DEFAULT_W, DEFAULT_H])
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const update = () => {
      const r = el.getBoundingClientRect()
      if (r.width > 0 && r.height > 0) setSize([Math.round(r.width), Math.round(r.height)])
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])
  return size
}

/** Kakao 키가 없을 때 쓰는 SVG 약식 지도 (그레이 톤). */
export default function SchematicMap({ origin, destination, routes, selectedId, overlay, inset = NO_INSET, onSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [W, H] = useContainerSize(wrapRef)
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
    // 패널·시트가 덮는 영역을 뺀 '보이는 창' 안에 경로를 맞춘다
    // 창이 좁으면 여백도 같이 줄인다 (핀 라벨 높이만큼은 남긴다)
    const freeW = W - inset.left - inset.right
    const freeH = H - inset.top - inset.bottom
    const padX = Math.max(24, Math.min(PAD, freeW / 5))
    const padY = Math.max(36, Math.min(PAD, freeH / 5))
    const padL = padX + inset.left, padR = padX + inset.right, padT = padY + inset.top, padB = padY + inset.bottom
    const innerW = Math.max(W - padL - padR, 40)
    const innerH = Math.max(H - padT - padB, 40)
    const scale = Math.min(innerW / spanX, innerH / spanY)
    return ([lat, lng]: number[]) => ({
      x: padL + (lng - minLng) * cos * scale + (innerW - spanX * scale) / 2,
      y: H - padB - (lat - minLat) * scale - (innerH - spanY * scale) / 2,
    })
  }, [routes, origin, destination, W, H, inset.top, inset.right, inset.bottom, inset.left])

  if (!project) {
    return (
      <div ref={wrapRef} className="schematic schematic--empty" role="img" aria-label="지도">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#b0b8c1" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z" /><path d="M9 3v15M15 6v15" />
        </svg>
      </div>
    )
  }
  const toPoints = (path: number[][]) => path.map((p) => { const q = project(p); return `${q.x.toFixed(1)},${q.y.toFixed(1)}` }).join(' ')
  const selected = routes.find((r) => r.id === selectedId) ?? routes[0]
  const pin = (p: { x: number; y: number }, label: string, dark: boolean) => (
    <g>
      <rect x={p.x - 22} y={p.y - 34} width={44} height={22} rx={11} fill={dark ? '#191f28' : '#fff'} stroke="#191f28" strokeWidth={1.5} />
      <text x={p.x} y={p.y - 19} fontSize={12} fontWeight={700} textAnchor="middle" fill={dark ? '#fff' : '#191f28'}>{label}</text>
      <circle cx={p.x} cy={p.y} r={5} fill={dark ? '#191f28' : '#fff'} stroke="#191f28" strokeWidth={2} />
    </g>
  )

  return (
    <div ref={wrapRef} className="schematic">
    <svg className="schematic__svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="약식 경로 지도">
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M40 0H0V40" fill="none" stroke="#e5e8eb" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width={W} height={H} fill="#f7f8fa" />
      <rect width={W} height={H} fill="url(#grid)" />
      {routes.filter((r) => r !== selected).map((r) => (
        <polyline key={r.id} points={toPoints(r.path)} fill="none" stroke={WALK_COLOR} strokeWidth={5} strokeOpacity={0.7} strokeLinecap="round"
          style={{ cursor: 'pointer' }} onClick={() => onSelect(r.id)} />
      ))}
      {selected && selected.legs.map((leg, i) => {
        if (leg.kind === 'walk' && overlay !== 'mode') {
          return leg.segments.map((seg, j) => (
            <polyline key={`${i}-${j}`} points={toPoints(seg.path)} fill="none" strokeWidth={8} strokeLinecap="round"
              stroke={overlay === 'grade' ? gradeColor(seg.grade_pct) : shadeColor(seg.shade_ratio)} />
          ))
        }
        if (leg.path.length < 2) return null
        return (
          <polyline key={i} points={toPoints(leg.path)} fill="none" strokeWidth={leg.kind === 'ride' ? 8 : 5} strokeLinecap="round" strokeLinejoin="round"
            stroke={legColor(leg)} strokeDasharray={leg.kind === 'walk' ? '2 9' : undefined} />
        )
      })}
      {origin && pin(project([origin.lat, origin.lng]), '출발', false)}
      {destination && pin(project([destination.lat, destination.lng]), '도착', true)}
    </svg>
    </div>
  )
}
