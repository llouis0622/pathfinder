import { useEffect, useRef } from 'react'
import { useKakaoMap, type KakaoOverlay } from '../hooks/useKakaoMap'
import { gradeColor, modeColor, shadeColor } from '../lib/format'
import type { MapOverlay, Place, Route } from '../types'
import SchematicMap from './SchematicMap'

type Props = {
  origin: Place | null
  destination: Place | null
  routes: Route[]
  selectedId: string | null
  overlay: MapOverlay
  onSelect: (id: string) => void
}

function pinHtml(label: string, color: string): string {
  return `<div style="transform:translateY(-4px);background:${color};color:#fff;font-weight:700;font-size:12px;padding:4px 8px;border-radius:999px;box-shadow:0 2px 6px rgba(0,0,0,.3);white-space:nowrap">${label}</div>`
}

export default function MapView({ origin, destination, routes, selectedId, overlay, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { map, status } = useKakaoMap(containerRef)
  const overlaysRef = useRef<KakaoOverlay[]>([])

  useEffect(() => {
    if (!map || !window.kakao) return
    const { maps } = window.kakao
    overlaysRef.current.forEach((o) => o.setMap(null))
    overlaysRef.current = []
    const add = (o: KakaoOverlay) => overlaysRef.current.push(o)
    const bounds = new maps.LatLngBounds()
    let hasBounds = false
    const extend = (lat: number, lng: number) => {
      bounds.extend(new maps.LatLng(lat, lng))
      hasBounds = true
    }

    if (origin) {
      add(new maps.CustomOverlay({ position: new maps.LatLng(origin.lat, origin.lng), content: pinHtml('출발', '#1d4ed8'), yAnchor: 1.4, zIndex: 20, map }))
      extend(origin.lat, origin.lng)
    }
    if (destination) {
      add(new maps.CustomOverlay({ position: new maps.LatLng(destination.lat, destination.lng), content: pinHtml('도착', '#dc2626'), yAnchor: 1.4, zIndex: 20, map }))
      extend(destination.lat, destination.lng)
    }

    const selected = routes.find((r) => r.id === selectedId) ?? routes[0]
    routes.forEach((route) => {
      if (route === selected) return
      add(new maps.Polyline({ path: route.path.map(([lat, lng]) => new maps.LatLng(lat, lng)), strokeWeight: 4, strokeColor: '#9ca3af', strokeOpacity: 0.7, zIndex: 1, map }))
    })
    if (selected) {
      selected.legs.forEach((leg) => {
        if (leg.kind === 'walk' && overlay !== 'mode') {
          leg.segments.forEach((seg) => {
            const color = overlay === 'grade' ? gradeColor(seg.grade_pct) : shadeColor(seg.shade_ratio)
            add(new maps.Polyline({ path: seg.path.map(([lat, lng]) => new maps.LatLng(lat, lng)), strokeWeight: 7, strokeColor: color, strokeOpacity: 0.95, zIndex: 10, map }))
          })
        } else if (leg.path.length >= 2) {
          add(new maps.Polyline({
            path: leg.path.map(([lat, lng]) => new maps.LatLng(lat, lng)),
            strokeWeight: leg.kind === 'ride' ? 8 : 6,
            strokeColor: modeColor(leg.kind === 'walk' ? 'walk' : leg.mode),
            strokeOpacity: 0.9,
            strokeStyle: leg.kind === 'ride' ? 'solid' : 'solid',
            zIndex: 10,
            map,
          }))
        }
        if (leg.kind === 'vertical' && leg.path[0]) {
          const icon = leg.facility === 'elevator' ? '🛗' : leg.facility === 'unknown' ? '❓' : '🪜'
          add(new maps.CustomOverlay({ position: new maps.LatLng(leg.path[0][0], leg.path[0][1]), content: `<div style="font-size:18px">${icon}</div>`, yAnchor: 0.5, zIndex: 15, map }))
        }
      })
      selected.path.forEach(([lat, lng]) => extend(lat, lng))
    }
    if (hasBounds) map.setBounds(bounds, 40, 40, 40, 40)
  }, [map, origin, destination, routes, selectedId, overlay])

  useEffect(() => {
    if (!map) return
    const onResize = () => map.relayout()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [map])

  if (status === 'no-key' || status === 'error') {
    return (
      <div className="map-fallback">
        <SchematicMap origin={origin} destination={destination} routes={routes} selectedId={selectedId} overlay={overlay} onSelect={onSelect} />
        <p className="map-fallback__note">
          {status === 'no-key'
            ? 'Kakao 지도 키(VITE_KAKAO_MAP_KEY)가 없어 약식 지도로 표시합니다.'
            : 'Kakao 지도 SDK를 불러오지 못해 약식 지도로 표시합니다.'}
        </p>
      </div>
    )
  }
  return <div ref={containerRef} className="map-canvas" role="application" aria-label="지도" />
}
