import { describe, expect, it } from 'vitest'
import { BADGE_LABELS, formatDistance, formatMinutes, gradeColor, legTitle, localInputToIso, shadeColor } from '../lib/format'
import { walkRoute } from './fixtures'

describe('format helpers', () => {
  it('labels every badge', () => {
    expect(Object.keys(BADGE_LABELS)).toHaveLength(7)
    expect(BADGE_LABELS.most_shade).toContain('그늘')
  })

  it('formats distance and minutes', () => {
    expect(formatDistance(673.6)).toBe('674m')
    expect(formatDistance(1500)).toBe('1.5km')
    expect(formatMinutes(20)).toBe('1분')
    expect(formatMinutes(3900)).toBe('1시간 5분')
  })

  it('maps grade and shade to colours', () => {
    expect(gradeColor(null)).toBe('#9ca3af')
    expect(gradeColor(2)).toBe('#22c55e')
    expect(gradeColor(-12)).toBe('#dc2626')
    expect(shadeColor(0)).toBe('rgb(249, 115, 22)')
    expect(shadeColor(1)).toBe('rgb(30, 58, 138)')
  })

  it('describes legs', () => {
    expect(legTitle(walkRoute.legs[0])).toBe('도보 300m · 6분')
    expect(legTitle(walkRoute.legs[1])).toBe('엘리베이터 · A역')
    expect(legTitle(walkRoute.legs[2])).toBe('지하철 1호선 · 3정거장 · 7분')
  })

  it('converts datetime-local to ISO with offset', () => {
    expect(localInputToIso('')).toBeNull()
    const iso = localInputToIso('2026-08-03T13:00')
    expect(iso).toMatch(/^2026-08-03T13:00:00[+-]\d{2}:\d{2}$/)
  })
})
