import { describe, expect, it } from 'vitest'
import { basemapStyle, boundsOf, graphLayers, layerVisibility, otherRoutesGeoJSON, selectedRouteGeoJSON, tilesUrl, OVERLAY_MIN_ZOOM } from '../lib/maplayers'
import type { Route } from '../types'
import { response } from './fixtures'

const ROUTES: Route[] = response.routes

describe('basemap', () => {
  it('uses VWorld when a key is set, OSM vector otherwise, and a custom style URL first', () => {
    const v = basemapStyle({ VITE_VWORLD_KEY: 'abc' })
    expect(v.provider).toBe('vworld')
    const style = v.style as { sources: Record<string, { tiles: string[] }> }
    expect(style.sources.vworld.tiles[0]).toContain('api.vworld.kr/req/wmts/1.0.0/abc/Base/{z}/{y}/{x}.png')
    expect(basemapStyle({})).toMatchObject({ provider: 'osm', style: expect.stringContaining('openfreemap') })
    expect(basemapStyle({ VITE_VWORLD_KEY: 'abc', VITE_BASEMAP_STYLE_URL: 'https://x/style.json' })).toEqual({ provider: 'custom', style: 'https://x/style.json' })
    expect(tilesUrl('http://localhost:5173')).toBe('http://localhost:5173/api/tiles/{z}/{x}/{y}.mvt')
  })
})

describe('graph layers', () => {
  it('hide below the overlay zoom and toggle by overlay', () => {
    const layers = graphLayers()
    expect(layers.every((l) => (l.minzoom ?? 0) >= OVERLAY_MIN_ZOOM)).toBe(true)
    expect(layerVisibility('grade')).toMatchObject({ 'g-edges-grade': true, 'g-edges-shade': false, 'g-edges-base': false, 'g-facilities': true })
    expect(layerVisibility('shade')['g-edges-shade']).toBe(true)
    expect(layerVisibility('facility')).toMatchObject({ 'g-edges-stairs': true, 'g-edges-base': true })
    expect(layerVisibility('mode')).toMatchObject({ 'g-edges-grade': false, 'g-edges-shade': false, 'g-edges-stairs': false })
    expect(Object.keys(layerVisibility('mode')).sort()).toEqual(layers.map((l) => l.id).sort())
  })
})

describe('route geojson', () => {
  it('splits the selected route by leg and colours walk segments in grade/shade overlays', () => {
    const other = otherRoutesGeoJSON(ROUTES, ROUTES[0].id)
    expect(other.features.map((f) => f.properties.id)).toEqual(ROUTES.slice(1).map((r) => r.id))
    const sel = selectedRouteGeoJSON(ROUTES[0], 'mode')
    expect(sel.features.length).toBe(ROUTES[0].legs.filter((l) => l.path.length >= 2).length)
    expect(sel.features.some((f) => f.properties.dashed)).toBe(true)
    const graded = selectedRouteGeoJSON(ROUTES[0], 'grade')
    const walkSegments = ROUTES[0].legs.filter((l) => l.kind === 'walk').reduce((a, l) => a + l.segments.filter((s) => s.path.length >= 2).length, 0)
    expect(graded.features.filter((f) => f.properties.id.includes('-')).length).toBe(walkSegments)
    expect(selectedRouteGeoJSON(null, 'mode').features).toEqual([])
    expect(boundsOf([[129.06, 35.15], [129.07, 35.16]])).toEqual([[129.06, 35.15], [129.07, 35.16]])
    expect(boundsOf([])).toBeNull()
  })
})

describe('fitPadding', () => {
  it('keeps a minimum visible window when the panel and sheet cover most of a phone screen', async () => {
    const { fitPadding } = await import('../lib/maplayers')
    const wide = fitPadding({ clientWidth: 1440, clientHeight: 900 }, { top: 0, right: 0, bottom: 0, left: 432 })
    expect(wide).toEqual({ top: 48, right: 48, bottom: 48, left: 480 })
    const phone = fitPadding({ clientWidth: 390, clientHeight: 844 }, { top: 233, right: 0, bottom: 422, left: 0 })
    expect(phone.top + phone.bottom).toBeLessThanOrEqual(844 - 120)
    expect(phone.top).toBeGreaterThan(0)
    expect(phone.top / phone.bottom).toBeCloseTo((233 + 48) / (422 + 48), 1)
  })
})
