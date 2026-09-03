// 백엔드·엔진 응답 타입. routes[] 는 엔진 RouteOut(engine/app/routes/schemas.py)과 1:1 이다.

export type ProfileId = 'wheelchair' | 'elderly' | 'walking_aid' | 'visually_impaired'
export type WeatherFlag = 'heat' | 'heatwave' | 'cold' | 'coldwave' | 'rain' | 'bad_air' | 'windy'

export type LatLng = { lat: number; lng: number }
export type Place = {
  id: string
  name: string
  address: string
  lat: number
  lng: number
  category: string
  source: string
}

export type Profile = { id: ProfileId; label: string; description?: string; speed_mps?: number | null }

export type SlopeSegment = {
  path: number[][]
  grade_pct: number | null
  distance_m: number
  shade_ratio: number
  stairs: boolean
  surface: string
  crossing: string
}

export type Leg = {
  kind: 'walk' | 'ride' | 'vertical'
  mode: string
  path: number[][]
  distance_m: number
  duration_s: number
  wait_s: number
  route_id: string
  route_name: string
  from_name: string
  to_name: string
  stop_count: number
  low_floor_ratio: number | null
  facility: '' | 'elevator' | 'escalator' | 'stairs' | 'unknown'
  station_name: string
  verified: boolean | null
  uphill_m: number
  downhill_m: number
  max_grade_pct: number | null
  stairs_count: number
  step_count: number
  shade_ratio: number | null
  unshaded_m: number
  crossings: number
  segments: SlopeSegment[]
}

export type RouteFeatures = {
  total_duration_s: number
  walk_distance_m: number
  walk_duration_s: number
  ride_duration_s: number
  wait_duration_s: number
  boardings: number
  transfers: number
  max_grade_pct: number | null
  avg_grade_pct: number | null
  uphill_m: number
  downhill_m: number
  stairs_count: number
  total_steps: number
  elevator_count: number
  unverified_vertical_count: number
  shade_ratio: number | null
  unshaded_walk_m: number
  crossings: number
  rough_surface_m: number
  modes: string[]
  generalized_cost_s: number
}

export type Badge =
  | 'fastest'
  | 'shortest_walk'
  | 'gentlest_slope'
  | 'most_shade'
  | 'fewest_transfers'
  | 'stair_free'
  | 'elevator_confirmed'

export type Route = {
  id: string
  rank: number
  summary: string
  badges: Badge[]
  cautions: string[]
  total_duration_min: number
  walk_distance_m: number
  transfers: number
  origin_algorithm: string
  features: RouteFeatures
  legs: Leg[]
  path: number[][]
}

export type Weather = {
  source: string
  observed_at: string | null
  forecast_for: string | null
  temp_c: number | null
  feels_like_c: number | null
  precipitation_mm: number | null
  wind_ms: number | null
  pm10: number | null
  sky: string
  flags: WeatherFlag[]
  note: string
}

export type SearchMetadata = {
  profile: string
  profile_label: string
  weather_flags: string[]
  departure_at: string | null
  preferences?: { avoid_slope: boolean; prefer_shade: boolean }
  shade_status: string
  shade_note: string
  building_height_coverage: number | null
  elevation_resolution_m: number
  elapsed_ms: number
  backend_elapsed_ms?: number
  [key: string]: unknown
}

export type RouteSearchRequest = {
  origin: LatLng & { name: string }
  destination: LatLng & { name: string }
  profile: ProfileId
  prefer_shade: boolean
  departure_at?: string | null
  options?: { k?: number; time_budget_s?: number; seed?: number }
}

export type RouteSearchResponse = {
  request_id: string
  profile: ProfileId
  departure_at: string | null
  prefer_shade: boolean
  weather: Weather
  routes: Route[]
  metadata: SearchMetadata
}

export type MapOverlay = 'mode' | 'grade' | 'shade'
