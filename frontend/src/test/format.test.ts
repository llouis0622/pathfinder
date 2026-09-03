import { describe, expect, it } from 'vitest'
import { BADGE_LABELS, formatDistance, formatDuration, formatMinutes, gradeColor, legColor, legTitle, routeSummary, shadeColor, weatherLine } from '../lib/format'
import { response, walkRoute } from './fixtures'

describe('format helpers', () => {
  it('labels every badge briefly', () => {
    expect(Object.keys(BADGE_LABELS)).toHaveLength(7)
    expect(BADGE_LABELS.gentlest_slope).toBe('경사 완만')
  })

  it('formats distance and time', () => {
    expect(formatDistance(673.6)).toBe('674m')
    expect(formatDistance(1500)).toBe('1.5km')
    expect(formatMinutes(20)).toBe('1분')
    expect(formatMinutes(3900)).toBe('1시간 5분')
    expect(formatDuration(21.8)).toEqual({ value: '22', unit: '분' })
    expect(formatDuration(75)).toEqual({ value: '1시간 15', unit: '분' })
  })

  it('maps grade, shade and legs to monochrome-first colours', () => {
    expect(gradeColor(null)).toBe('#b0b8c1')
    expect(gradeColor(2)).toBe('#191f28')
    expect(gradeColor(-12)).toBe('#e5484d')
    expect(shadeColor(0)).toBe('rgb(213, 218, 224)')
    expect(shadeColor(1)).toBe('rgb(25, 31, 40)')
    expect(legColor(walkRoute.legs[0])).toBe('#191f28')
    expect(legColor(walkRoute.legs[2])).toBe('#F06A00')
    expect(legColor({ kind: 'ride', mode: 'bus', route_name: '77번' })).toBe('#4e5968')
  })

  it('describes legs and summarises a route without vertical moves', () => {
    expect(legTitle(walkRoute.legs[0])).toBe('도보 6분')
    expect(legTitle(walkRoute.legs[1])).toBe('엘리베이터')
    expect(legTitle(walkRoute.legs[3])).toBe('엘리베이터 확인 필요')
    expect(routeSummary(walkRoute.legs)).toBe('도보 6분 · 1호선 3정거장 · 도보 6분')
  })

  it('builds a compact weather line and hides it when unavailable', () => {
    expect(weatherLine(response.weather)).toBe('34° · 맑음 · 폭염')
    expect(weatherLine({ ...response.weather, source: 'unavailable' })).toBeNull()
    expect(weatherLine({ ...response.weather, flags: [], sky: 'rain' })).toBe('34° · 비')
  })
})
