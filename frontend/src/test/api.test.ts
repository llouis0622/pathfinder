import { afterEach, describe, expect, it, vi } from 'vitest'
import { searchPlaces, searchRoutes } from '../api'

describe('api client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('posts route requests to /api/route', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ routes: [] }), { status: 200 }))
    await searchRoutes({
      origin: { lat: 1, lng: 2, name: 'a' }, destination: { lat: 3, lng: 4, name: 'b' }, profile: 'elderly', prefer_shade: true,
    })
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe('/api/route')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toMatchObject({ profile: 'elderly', prefer_shade: true })
  })

  it('encodes place queries and surfaces backend detail on errors', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: '경로 없음' }), { status: 422 }))
    await expect(searchPlaces('부산 역', { lat: 35, lng: 129 })).rejects.toMatchObject({ status: 422, message: '경로 없음' })
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/place/search?query=%EB%B6%80%EC%82%B0+%EC%97%AD&lat=35&lng=129')
  })
})
