import { beforeEach, describe, expect, it } from 'vitest'
import { legSentence, resultsSpeech, routeSpeech } from '../lib/a11y'
import { localFavorites, localRecent, onboarding, toPlace } from '../lib/storage'
import { response } from './fixtures'

const route = response.routes[0]

describe('speech text', () => {
  it('describes legs with facilities and cautions first', () => {
    const text = routeSpeech(route, '서면역', '하단역')
    expect(text.startsWith('서면역에서 하단역까지, 총 ')).toBe(true)
    expect(text).toContain('도착입니다.')
    const walk = legSentence(route.legs[0], 0)
    expect(walk).toMatch(/^1번째, 도보 /)
    const ride = route.legs.find((l) => l.kind === 'ride')!
    expect(legSentence(ride, 2)).toContain('탑승')
    expect(resultsSpeech(3, route)).toContain('경로 3개')
    expect(resultsSpeech(0, null)).toBe('경로를 찾지 못했어요.')
  })
})

describe('local favorites and recent', () => {
  beforeEach(() => localStorage.clear())

  it('saves favorites by label, keeps recent unique and marks onboarding', () => {
    const a = toPlace({ name: '우리집', lat: 35.1, lng: 129.0 })
    const b = toPlace({ name: '회사', lat: 35.2, lng: 129.1 })
    localFavorites.save('집', a)
    localFavorites.save('집', b)
    expect(localFavorites.list()).toHaveLength(1)
    expect(localFavorites.list()[0].name).toBe('회사')
    const id = localFavorites.list()[0].id
    expect(localFavorites.remove(id)).toEqual([])
    localRecent.push(a, b, 'elderly')
    localRecent.push(a, b, 'wheelchair')
    localRecent.push(b, a, 'elderly')
    expect(localRecent.list()).toHaveLength(2)
    expect(localRecent.list()[0].origin.name).toBe('회사')
    expect(onboarding.seen()).toBe(false)
    onboarding.dismiss()
    expect(onboarding.seen()).toBe(true)
  })
})
