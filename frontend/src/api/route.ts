import axios from 'axios'
import type { RouteRequest, RouteResponse } from '../types'

const backendUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

// 경로 추천 API 호출
export async function fetchRoute(payload: RouteRequest): Promise<RouteResponse> {
  const { data } = await axios.post<RouteResponse>(`${backendUrl}/api/route`, payload)
  return data
}
