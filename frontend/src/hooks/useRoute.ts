import { useState } from 'react'
import { fetchRoute } from '../api/route'
import type { Place, RouteResult, RouteWeights } from '../types'

// 경로 탐색 훅
export function useRoute() {
  const [routes, setRoutes] = useState<RouteResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function search(
    origin: Place,
    destination: Place,
    profile: string,
    weights: RouteWeights,
  ) {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchRoute({
        origin: { lat: origin.lat, lng: origin.lng, name: origin.name },
        destination: { lat: destination.lat, lng: destination.lng, name: destination.name },
        profile,
        weights,
      })
      setRoutes(res.routes)
    } catch {
      setError('경로를 불러오는 데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  function clear() {
    setRoutes([])
    setError(null)
  }

  return { routes, loading, error, search, clear }
}
