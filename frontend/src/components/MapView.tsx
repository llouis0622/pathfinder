/**
 * MapLibre 지도. 배경(VWorld 또는 OSM) 위에 우리 그래프 타일(경사·계단·턱·시설·정류장)을 얹고,
 * 확대(줌 15+)했을 때만 레이어를 보여 준다. 그늘은 화면 범위와 출발 시각으로 실시간 계산해 feature-state 로 칠한다.
 * WebGL 이 없거나 지도 생성에 실패하면 SVG 약식 지도로 대체한다.
 */
import maplibregl, { type GeoJSONSource, type Map as MLMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchShade } from '../api'
import { BLANK_STYLE, BUSAN_CENTER, GRAPH_MIN_ZOOM, GRAPH_SOURCE, SHADE_MIN_ZOOM, basemapStyle, boundsOf, fitPadding, graphLayers, layerVisibility,
  otherRoutesGeoJSON, routeLayers, selectedRouteGeoJSON, tilesUrl } from '../lib/maplayers'
import type { MapInset, MapOverlay, Place, Route } from '../types'
import SchematicMap from './SchematicMap'

export type LocatedPoint = { lat: number; lng: number; accuracy_m: number }

type Props = {
  origin: Place | null
  destination: Place | null
  routes: Route[]
  selectedId: string | null
  overlay: MapOverlay
  inset?: MapInset
  departureAt?: string | null
  onSelect: (id: string) => void
  onLocate?: (p: LocatedPoint) => void
  onZoom?: (zoom: number) => void
}

const NO_INSET: MapInset = { top: 0, right: 0, bottom: 0, left: 0 }
const STYLE_TIMEOUT_MS = 8000
const READY_TIMEOUT_MS = 15000   // 이때까지 지도가 못 뜨면(워커·WebGL 차단 등) 약식 지도로

function pinElement(label: string, dark: boolean): HTMLElement {
  const el = document.createElement('div')
  el.className = `map-pin${dark ? ' map-pin--dark' : ''}`
  el.textContent = label
  return el
}

function webglSupported(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

export default function MapView({ origin, destination, routes, selectedId, overlay, inset = NO_INSET, departureAt, onSelect, onLocate, onZoom }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const shadeAbortRef = useRef<AbortController | null>(null)
  const shadedIdsRef = useRef<Set<string>>(new Set())
  const callbacksRef = useRef({ onSelect, onLocate, onZoom })
  callbacksRef.current = { onSelect, onLocate, onZoom }
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(() => typeof window === 'undefined' || !webglSupported())
  const selected = useMemo(() => routes.find((r) => r.id === selectedId) ?? routes[0] ?? null, [routes, selectedId])

  // ---- 지도 생성 (한 번)
  useEffect(() => {
    if (failed || !containerRef.current) return
    let map: MLMap
    const { style } = basemapStyle(import.meta.env)
    try {
      map = new maplibregl.Map({ container: containerRef.current, style, center: BUSAN_CENTER, zoom: 12, maxZoom: 20, attributionControl: { compact: true } })
    } catch {
      setFailed(true)
      return
    }
    mapRef.current = map
    let loaded = false
    let fellBack = false
    const fallbackToBlank = () => {
      if (loaded || fellBack) return
      fellBack = true
      map.setStyle(BLANK_STYLE)
    }
    // 배경 스타일을 못 받아오면(오프라인·키 오류) 빈 배경으로라도 우리 레이어를 띄운다
    map.on('error', (e: { error?: { status?: number; message?: string }; sourceId?: string }) => {
      if (!loaded && !e.sourceId) fallbackToBlank()
    })
    const timer = window.setTimeout(fallbackToBlank, STYLE_TIMEOUT_MS)
    const giveUp = window.setTimeout(() => { if (!loaded) setFailed(true) }, READY_TIMEOUT_MS)
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    const geolocate = new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true, timeout: 10000 }, trackUserLocation: true, showAccuracyCircle: true })
    map.addControl(geolocate, 'bottom-right')
    geolocate.on('geolocate', (e: { coords: { latitude: number; longitude: number; accuracy: number } }) => {
      callbacksRef.current.onLocate?.({ lat: e.coords.latitude, lng: e.coords.longitude, accuracy_m: e.coords.accuracy })
    })
    const install = () => {
      if (loaded) return
      loaded = true
      window.clearTimeout(timer)
      window.clearTimeout(giveUp)
      if (!map.getSource(GRAPH_SOURCE)) {
        map.addSource(GRAPH_SOURCE, { type: 'vector', tiles: [tilesUrl(window.location.origin)], minzoom: GRAPH_MIN_ZOOM, maxzoom: 18 })
        map.addSource('routes-other', { type: 'geojson', data: otherRoutesGeoJSON([], null) })
        map.addSource('route-selected', { type: 'geojson', data: selectedRouteGeoJSON(null, 'mode') })
        graphLayers().forEach((l) => map.addLayer(l))
        routeLayers().forEach((l) => map.addLayer(l))
        map.on('click', 'r-other', (e) => {
          const id = e.features?.[0]?.properties?.id
          if (typeof id === 'string') callbacksRef.current.onSelect(id)
        })
        map.on('mouseenter', 'r-other', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'r-other', () => { map.getCanvas().style.cursor = '' })
      }
      setReady(true)
    }
    map.on('load', install)
    map.on('style.load', () => { if (fellBack) install() })
    map.on('zoomend', () => callbacksRef.current.onZoom?.(map.getZoom()))
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => map.resize()) : null
    ro?.observe(containerRef.current)
    return () => {
      window.clearTimeout(timer)
      window.clearTimeout(giveUp)
      ro?.disconnect()
      map.remove()
      mapRef.current = null
    }
  }, [failed])

  // ---- 오버레이별 레이어 표시
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const vis = layerVisibility(overlay)
    Object.entries(vis).forEach(([id, on]) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none') })
  }, [overlay, ready])

  // ---- 경로·핀
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    ;(map.getSource('routes-other') as GeoJSONSource | undefined)?.setData(otherRoutesGeoJSON(routes, selected?.id ?? null))
    ;(map.getSource('route-selected') as GeoJSONSource | undefined)?.setData(selectedRouteGeoJSON(selected, overlay))
    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []
    const points: [number, number][] = []
    if (origin) {
      markersRef.current.push(new maplibregl.Marker({ element: pinElement('출발', false), anchor: 'bottom', offset: [0, -6] }).setLngLat([origin.lng, origin.lat]).addTo(map))
      points.push([origin.lng, origin.lat])
    }
    if (destination) {
      markersRef.current.push(new maplibregl.Marker({ element: pinElement('도착', true), anchor: 'bottom', offset: [0, -6] }).setLngLat([destination.lng, destination.lat]).addTo(map))
      points.push([destination.lng, destination.lat])
    }
    selected?.path.forEach(([lat, lng]) => points.push([lng, lat]))
    const bounds = boundsOf(points)
    if (!bounds) return
    // easeTo 의 padding 은 지도에 남아 다음 fit 을 망가뜨리므로, 한 점도 fitBounds 로 맞춘다
    const padding = fitPadding(map.getContainer(), inset)
    map.fitBounds(bounds, { padding, maxZoom: points.length === 1 ? 16 : 17, duration: 500 })
  }, [ready, origin, destination, routes, selected, overlay, inset.top, inset.right, inset.bottom, inset.left])

  // ---- 그늘: 화면 범위를 실시간 계산해 feature-state 로 칠한다
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (overlay !== 'shade') return
    let timer: number | undefined
    const refresh = async () => {
      if (map.getZoom() < SHADE_MIN_ZOOM) return
      shadeAbortRef.current?.abort()
      const ctrl = new AbortController()
      shadeAbortRef.current = ctrl
      const b = map.getBounds()
      try {
        const res = await fetchShade({ min_lat: b.getSouth(), min_lng: b.getWest(), max_lat: b.getNorth(), max_lng: b.getEast(), at: departureAt ?? undefined }, ctrl.signal)
        if (ctrl.signal.aborted) return
        Object.entries(res.ratios).forEach(([id, ratio]) => {
          map.setFeatureState({ source: GRAPH_SOURCE, sourceLayer: 'edges', id: Number(id) }, { shade: ratio })
          shadedIdsRef.current.add(id)
        })
      } catch {
        /* 범위가 넓거나 엔진이 없으면 그늘 없이 둔다 */
      }
    }
    const schedule = () => { window.clearTimeout(timer); timer = window.setTimeout(refresh, 250) }
    // 경로 소스 갱신·타일 하나하나가 아니라 그래프 타일 소스가 다 실렸을 때만 다시 계산한다
    const onSourceData = (e: maplibregl.MapSourceDataEvent) => { if (e.sourceId === GRAPH_SOURCE && e.isSourceLoaded) schedule() }
    // 시각이 바뀌면 이전에 칠한 값은 지워 두고 새로 받는다
    shadedIdsRef.current.forEach((id) => map.setFeatureState({ source: GRAPH_SOURCE, sourceLayer: 'edges', id: Number(id) }, { shade: null }))
    shadedIdsRef.current.clear()
    map.on('moveend', schedule)
    map.on('sourcedata', onSourceData)
    schedule()
    return () => { window.clearTimeout(timer); map.off('moveend', schedule); map.off('sourcedata', onSourceData); shadeAbortRef.current?.abort() }
  }, [overlay, ready, departureAt])

  if (failed) {
    return <SchematicMap origin={origin} destination={destination} routes={routes} selectedId={selectedId} overlay={overlay} inset={inset} onSelect={onSelect} />
  }
  return <div ref={containerRef} className="map-canvas" role="application" aria-label="지도" data-ready={ready ? '1' : '0'} />
}
