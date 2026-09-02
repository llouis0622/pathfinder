import { useEffect, useRef } from 'react'
import { useKakaoMap, type KakaoOverlay } from '../hooks/useKakaoMap'
import { WALK_COLOR, gradeColor, legColor, shadeColor } from '../lib/format'
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

function pinHtml(label: string, dark: boolean): string {
  const bg = dark ? '#191f28' : '#ffffff'
  const fg = dark ? '#ffffff' : '#191f28'
  return `<div style="transform:translateY(-6px);background:${bg};color:${fg};font-weight:700;font-size:12px;padding:5px 9px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.18);white-space:nowrap;border:1.5px solid #191f28">${label}</div>`
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
    const selected = routes.find((r) => r.id === selectedId) ?? routes[0]
    routes.forEach((route) => {
      if (route === selected) return
      add(new maps.Polyline({ path: route.path.map(([lat, lng]) => new maps.LatLng(lat, lng)), strokeWeight: 5, strokeColor: WALK_COLOR, strokeOpacity: 0.6, zIndex: 1, map }))
    })
    if (selected) {
      selected.legs.forEach((leg) => {
        if (leg.kind === 'walk' && overlay !== 'mode') {
          leg.segments.forEach((seg) => {
            const color = overlay === 'grade' ? gradeColor(seg.grade_pct) : shadeColor(seg.shade_ratio)
            add(new maps.Polyline({ path: seg.path.map(([lat, lng]) => new maps.LatLng(lat, lng)), strokeWeight: 8, strokeColor: color, strokeOpacity: 0.95, zIndex: 10, map }))
          })
        } else if (leg.path.length >= 2) {
          add(new maps.Polyline({
            path: leg.path.map(([lat, lng]) => new maps.LatLng(lat, lng)),
            strokeWeight: leg.kind === 'ride' ? 8 : 6,
            strokeColor: legColor(leg),
            strokeOpacity: 0.95,
            strokeStyle: leg.kind === 'walk' ? 'shortdash' : 'solid',
            zIndex: 10,
            map,
          }))
        }
      })
      selected.path.forEach(([lat, lng]) => extend(lat, lng))
    }
    if (origin) {
      add(new maps.CustomOverlay({ position: new maps.LatLng(origin.lat, origin.lng), content: pinHtml('출발', false), yAnchor: 1.3, zIndex: 20, map }))
      extend(origin.lat, origin.lng)
    }
    if (destination) {
      add(new maps.CustomOverlay({ position: new maps.LatLng(destination.lat, destination.lng), content: pinHtml('도착', true), yAnchor: 1.3, zIndex: 20, map }))
      extend(destination.lat, destination.lng)
    }
    if (hasBounds) map.setBounds(bounds, 48, 48, 48, 48)
  }, [map, origin, destination, routes, selectedId, overlay])

  useEffect(() => {
    if (!map) return
    const onResize = () => map.relayout()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [map])

  if (status === 'no-key' || status === 'error') {
    return <SchematicMap origin={origin} destination={destination} routes={routes} selectedId={selectedId} overlay={overlay} onSelect={onSelect} />
  }
  return <div ref={containerRef} className="map-canvas" role="application" aria-label="지도" />
}
