/**
 * MapLibre 지도 구성 (순수 함수). 배경 지도 선택, 그래프 레이어 정의, 오버레이별 표시 여부, 경로 GeoJSON.
 * 렌더러(MapView)와 분리해 두어 단위 테스트가 가능하다.
 */
import type { FilterSpecification, LayerSpecification, StyleSpecification } from 'maplibre-gl'
import type { Leg, MapInset, MapOverlay, Route } from '../types'
import { gradeColor, legColor, shadeColor } from './format'

export type BasemapEnv = { VITE_VWORLD_KEY?: string; VITE_BASEMAP_STYLE_URL?: string }

export const BUSAN_CENTER: [number, number] = [129.0756, 35.1796]
export const GRAPH_SOURCE = 'graph'
export const GRAPH_MIN_ZOOM = 14          // 타일이 존재하는 최소 줌
export const OVERLAY_MIN_ZOOM = 15        // 경사·시설 레이어가 켜지는 줌 (그 아래는 배경 지도만)
export const SHADE_MIN_ZOOM = 16          // 그늘은 범위 계산이 있어 더 확대했을 때만
export const LABEL_MIN_ZOOM = 17

export const OPENFREEMAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
export const GLYPHS = 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf'

export const BLANK_STYLE: StyleSpecification = {
  version: 8,
  glyphs: GLYPHS,
  sources: {},
  layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f2f4f6' } }],
}

/** 배경 지도: VWorld 키가 있으면 VWorld 일반 지도, 아니면 OpenFreeMap(OSM 벡터). 스타일 URL 을 직접 줄 수도 있다. */
export function basemapStyle(env: BasemapEnv): { style: StyleSpecification | string; provider: 'vworld' | 'osm' | 'custom' } {
  if (env.VITE_BASEMAP_STYLE_URL) return { style: env.VITE_BASEMAP_STYLE_URL, provider: 'custom' }
  const key = env.VITE_VWORLD_KEY?.trim()
  if (key) {
    return {
      provider: 'vworld',
      style: {
        version: 8,
        glyphs: GLYPHS,
        sources: {
          vworld: {
            type: 'raster',
            tiles: [`https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(key)}/Base/{z}/{y}/{x}.png`],
            tileSize: 256,
            maxzoom: 19,
            attribution: '© 국토교통부 VWorld',
          },
        },
        layers: [{ id: 'vworld', type: 'raster', source: 'vworld' }],
      },
    }
  }
  return { style: OPENFREEMAP_STYLE, provider: 'osm' }
}

export function tilesUrl(origin: string): string {
  return `${origin}/api/tiles/{z}/{x}/{y}.mvt`
}

// ---------------------------------------------------------------- 그래프 레이어
const GRADE_COLOR = ['case', ['has', 'max_grade'],
  ['step', ['abs', ['get', 'max_grade']], '#191f28', 3, '#6b7684', 6, '#f59e0b', 10, '#e5484d'], '#b0b8c1'] as unknown as string
const SHADE_COLOR = ['case', ['>=', ['coalesce', ['feature-state', 'shade'], -1], 0],
  ['interpolate', ['linear'], ['feature-state', 'shade'], 0, '#d5dae0', 1, '#191f28'], '#e5e8eb'] as unknown as string
export const FACILITY_COLORS: Record<string, string> = {
  stairs: '#e5484d', elevator: '#0f7a53', escalator: '#2a78d6', vertical: '#8b95a1', kerb: '#f59e0b', crossing: '#191f28',
}
export const FACILITY_LABELS: Record<string, string> = { stairs: '계단', elevator: 'EV', escalator: 'ES', vertical: '수직', kerb: '턱', crossing: '횡단' }
const facilityMatch = (map: Record<string, string>, fallback: string) =>
  ['match', ['get', 'type'], ...Object.entries(map).flat(), fallback] as unknown as string

/** 오버레이별 레이어. 모든 레이어는 minzoom 이 있어 축소하면 사라지고 배경 지도만 남는다. */
export function graphLayers(): LayerSpecification[] {
  const walk = ['in', ['get', 'kind'], ['literal', ['walk', 'link']]] as unknown as FilterSpecification
  const layers: LayerSpecification[] = [
    { id: 'g-edges-base', type: 'line', source: GRAPH_SOURCE, 'source-layer': 'edges', minzoom: OVERLAY_MIN_ZOOM, filter: walk,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#c9cfd6', 'line-width': ['interpolate', ['linear'], ['zoom'], 15, 1.2, 18, 3.5], 'line-opacity': 0.9 } },
    { id: 'g-edges-grade', type: 'line', source: GRAPH_SOURCE, 'source-layer': 'edges', minzoom: OVERLAY_MIN_ZOOM, filter: walk,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': GRADE_COLOR, 'line-width': ['interpolate', ['linear'], ['zoom'], 15, 2, 18, 6], 'line-opacity': 0.95 } },
    { id: 'g-edges-shade', type: 'line', source: GRAPH_SOURCE, 'source-layer': 'edges', minzoom: SHADE_MIN_ZOOM, filter: walk,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': SHADE_COLOR, 'line-width': ['interpolate', ['linear'], ['zoom'], 16, 3, 19, 8], 'line-opacity': 0.95 } },
    { id: 'g-edges-stairs', type: 'line', source: GRAPH_SOURCE, 'source-layer': 'edges', minzoom: OVERLAY_MIN_ZOOM,
      filter: ['==', ['get', 'stairs'], 1],
      layout: { 'line-cap': 'butt' },
      paint: { 'line-color': '#e5484d', 'line-width': ['interpolate', ['linear'], ['zoom'], 15, 2, 18, 6], 'line-dasharray': [0.8, 0.8] } },
    { id: 'g-facilities', type: 'circle', source: GRAPH_SOURCE, 'source-layer': 'facilities', minzoom: OVERLAY_MIN_ZOOM,
      paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 15, 3, 19, 8], 'circle-color': facilityMatch(FACILITY_COLORS, '#8b95a1'),
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5, 'circle-opacity': ['case', ['==', ['get', 'verified'], 1], 1, 0.85] } },
    { id: 'g-facilities-label', type: 'symbol', source: GRAPH_SOURCE, 'source-layer': 'facilities', minzoom: LABEL_MIN_ZOOM,
      layout: { 'text-field': facilityMatch(FACILITY_LABELS, '시설'), 'text-size': 11, 'text-offset': [0, 1.1], 'text-anchor': 'top',
        'text-font': ['Noto Sans Regular'], 'text-allow-overlap': false },
      paint: { 'text-color': '#4e5968', 'text-halo-color': '#ffffff', 'text-halo-width': 1.2 } },
    { id: 'g-stops', type: 'circle', source: GRAPH_SOURCE, 'source-layer': 'stops', minzoom: OVERLAY_MIN_ZOOM,
      paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 15, 3.5, 19, 7], 'circle-color': '#ffffff', 'circle-stroke-color': '#191f28',
        'circle-stroke-width': 2 } },
    { id: 'g-stops-label', type: 'symbol', source: GRAPH_SOURCE, 'source-layer': 'stops', minzoom: SHADE_MIN_ZOOM,
      layout: { 'text-field': ['get', 'name'], 'text-size': 11.5, 'text-offset': [0, 1], 'text-anchor': 'top', 'text-font': ['Noto Sans Regular'] },
      paint: { 'text-color': '#191f28', 'text-halo-color': '#ffffff', 'text-halo-width': 1.4 } },
  ]
  return layers
}

/** 오버레이에 따라 켜지는 레이어. 배경 네트워크는 항상, 경사/그늘은 해당 모드, 시설·계단은 시설 모드에서 강조된다. */
export function layerVisibility(overlay: MapOverlay): Record<string, boolean> {
  return {
    'g-edges-base': overlay === 'mode' || overlay === 'facility',
    'g-edges-grade': overlay === 'grade',
    'g-edges-shade': overlay === 'shade',
    'g-edges-stairs': overlay === 'facility',
    'g-facilities': true,
    'g-facilities-label': true,
    'g-stops': true,
    'g-stops-label': true,
  }
}

// ---------------------------------------------------------------- 경로 GeoJSON
type LineFeature = GeoJSON.Feature<GeoJSON.LineString, { id: string; color: string; dashed: boolean; width: number }>

const toLine = (path: number[][]) => path.map(([lat, lng]) => [lng, lat])

export function otherRoutesGeoJSON(routes: Route[], selectedId: string | null): GeoJSON.FeatureCollection<GeoJSON.LineString, { id: string }> {
  return {
    type: 'FeatureCollection',
    features: routes.filter((r) => r.id !== selectedId && r.path.length >= 2)
      .map((r) => ({ type: 'Feature', properties: { id: r.id }, geometry: { type: 'LineString', coordinates: toLine(r.path) } })),
  }
}

/** 선택 경로: 구간별 색. 경사/그늘 오버레이에서는 도보 구간을 세그먼트 값으로 칠한다. */
export function selectedRouteGeoJSON(route: Route | null, overlay: MapOverlay): GeoJSON.FeatureCollection<GeoJSON.LineString, LineFeature['properties']> {
  const features: LineFeature[] = []
  if (route) {
    route.legs.forEach((leg: Leg, i) => {
      if (leg.kind === 'walk' && (overlay === 'grade' || overlay === 'shade')) {
        leg.segments.forEach((seg, j) => {
          if (seg.path.length < 2) return
          features.push({ type: 'Feature', properties: { id: `${i}-${j}`, color: overlay === 'grade' ? gradeColor(seg.grade_pct) : shadeColor(seg.shade_ratio), dashed: false, width: 8 },
            geometry: { type: 'LineString', coordinates: toLine(seg.path) } })
        })
        return
      }
      if (leg.path.length < 2) return
      features.push({ type: 'Feature', properties: { id: String(i), color: legColor(leg), dashed: leg.kind === 'walk', width: leg.kind === 'ride' ? 8 : 6 },
        geometry: { type: 'LineString', coordinates: toLine(leg.path) } })
    })
  }
  return { type: 'FeatureCollection', features }
}

export function routeLayers(): LayerSpecification[] {
  return [
    { id: 'r-other', type: 'line', source: 'routes-other', layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#b0b8c1', 'line-width': 5, 'line-opacity': 0.7 } },
    { id: 'r-sel-casing', type: 'line', source: 'route-selected', layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': ['+', ['get', 'width'], 4], 'line-opacity': 0.9 } },
    { id: 'r-sel-solid', type: 'line', source: 'route-selected', filter: ['==', ['get', 'dashed'], false], layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ['get', 'color'], 'line-width': ['get', 'width'] } },
    { id: 'r-sel-dashed', type: 'line', source: 'route-selected', filter: ['==', ['get', 'dashed'], true], layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ['get', 'color'], 'line-width': ['get', 'width'], 'line-dasharray': [0.2, 1.8] } },
  ]
}

/** 경로·출발·도착을 모두 담는 경계 [[minLng, minLat], [maxLng, maxLat]]. */
export function boundsOf(points: [number, number][]): [[number, number], [number, number]] | null {
  if (points.length === 0) return null
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity
  for (const [lng, lat] of points) {
    minLng = Math.min(minLng, lng); maxLng = Math.max(maxLng, lng); minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat)
  }
  return [[minLng, minLat], [maxLng, maxLat]]
}

// ---------------------------------------------------------------- 경로 맞추기 여백
export const FIT_PAD = 48

/** 패널·시트가 덮는 만큼 여백을 두되, 여백 합이 화면을 넘으면(작은 폰) 보이는 창이 최소 크기는 남도록 비례해서 줄인다. */
export function fitPadding(container: { clientWidth: number; clientHeight: number }, inset: MapInset, minWindow = 120): { top: number; right: number; bottom: number; left: number } {
  let top = FIT_PAD + inset.top, bottom = FIT_PAD + inset.bottom, left = FIT_PAD + inset.left, right = FIT_PAD + inset.right
  const h = container.clientHeight || 0, w = container.clientWidth || 0
  if (h > 0 && top + bottom > h - minWindow) {
    const k = Math.max(0, h - minWindow) / (top + bottom)
    top = Math.floor(top * k); bottom = Math.floor(bottom * k)
  }
  if (w > 0 && left + right > w - minWindow) {
    const k = Math.max(0, w - minWindow) / (left + right)
    left = Math.floor(left * k); right = Math.floor(right * k)
  }
  return { top, right, bottom, left }
}
