import axios from 'axios'
import type { PlaceResponse } from '../types'

const backendUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

// 장소 검색 API 호출
export async function searchPlaces(
  query: string,
  lat?: number,
  lng?: number,
): Promise<PlaceResponse> {
  const params: Record<string, string | number> = { query }
  if (lat !== undefined) params.lat = lat
  if (lng !== undefined) params.lng = lng

  const { data } = await axios.get<PlaceResponse>(`${backendUrl}/api/place/search`, { params })
  return data
}
