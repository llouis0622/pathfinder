import type { Route, RouteSearchResponse } from '../types'

export const walkRoute: Route = {
  id: 'route_1',
  rank: 1,
  summary: '도보 6분 · 엘리베이터 · 지하철 1호선 3정거장 · 엘리베이터 · 도보 5분',
  badges: ['fastest', 'stair_free', 'elevator_confirmed'],
  cautions: ['그늘 없는 도보 674m (더위 주의)'],
  total_duration_min: 21.8,
  walk_distance_m: 673.6,
  transfers: 0,
  origin_algorithm: 'seed',
  features: {
    total_duration_s: 1308, walk_distance_m: 673.6, walk_duration_s: 660, ride_duration_s: 420, wait_duration_s: 210, boardings: 1,
    transfers: 0, max_grade_pct: 0.3, avg_grade_pct: 0.1, uphill_m: 1, downhill_m: 1, stairs_count: 0, total_steps: 0, elevator_count: 2,
    unverified_vertical_count: 0, shade_ratio: 0.12, unshaded_walk_m: 592, crossings: 1, rough_surface_m: 0, modes: ['walk', 'subway'],
    generalized_cost_s: 2000.9,
  },
  legs: [
    { kind: 'walk', mode: 'walk', path: [[35.15, 129.06], [35.151, 129.061]], distance_m: 300, duration_s: 330, wait_s: 0, route_id: '', route_name: '', from_name: '', to_name: '', stop_count: 0, low_floor_ratio: null, facility: '', station_name: '', verified: null, uphill_m: 1, downhill_m: 0, max_grade_pct: 4.2, stairs_count: 0, step_count: 0, shade_ratio: 0.2, unshaded_m: 240, crossings: 1, segments: [{ path: [[35.15, 129.06], [35.151, 129.061]], grade_pct: 0.3, distance_m: 300, shade_ratio: 0.2, stairs: false, surface: 'asphalt', crossing: '' }] },
    { kind: 'vertical', mode: 'subway', path: [[35.151, 129.061], [35.151, 129.061]], distance_m: 0, duration_s: 90, wait_s: 0, route_id: '', route_name: '', from_name: '', to_name: '', stop_count: 0, low_floor_ratio: null, facility: 'elevator', station_name: 'A역', verified: true, uphill_m: 0, downhill_m: 0, max_grade_pct: null, stairs_count: 0, step_count: 0, shade_ratio: null, unshaded_m: 0, crossings: 0, segments: [] },
    { kind: 'ride', mode: 'subway', path: [[35.151, 129.061], [35.151, 129.07]], distance_m: 1500, duration_s: 420, wait_s: 210, route_id: 'subway-1-up', route_name: '1호선', from_name: 'A역', to_name: 'D역', stop_count: 3, low_floor_ratio: null, facility: '', station_name: '', verified: null, uphill_m: 0, downhill_m: 0, max_grade_pct: null, stairs_count: 0, step_count: 0, shade_ratio: null, unshaded_m: 0, crossings: 0, segments: [] },
    { kind: 'vertical', mode: 'subway', path: [[35.151, 129.07], [35.151, 129.07]], distance_m: 0, duration_s: 90, wait_s: 0, route_id: '', route_name: '', from_name: '', to_name: '', stop_count: 0, low_floor_ratio: null, facility: 'unknown', station_name: 'D역', verified: null, uphill_m: 0, downhill_m: 0, max_grade_pct: null, stairs_count: 0, step_count: 0, shade_ratio: null, unshaded_m: 0, crossings: 0, segments: [] },
    { kind: 'walk', mode: 'walk', path: [[35.151, 129.07], [35.152, 129.071]], distance_m: 373.6, duration_s: 330, wait_s: 0, route_id: '', route_name: '', from_name: '', to_name: '', stop_count: 0, low_floor_ratio: null, facility: '', station_name: '', verified: null, uphill_m: 0, downhill_m: 1, max_grade_pct: 0.3, stairs_count: 0, step_count: 0, shade_ratio: 0.05, unshaded_m: 352, crossings: 0, segments: [{ path: [[35.151, 129.07], [35.152, 129.071]], grade_pct: -0.3, distance_m: 373.6, shade_ratio: 0.05, stairs: false, surface: 'asphalt', crossing: '' }] },
  ],
  path: [[35.15, 129.06], [35.151, 129.061], [35.151, 129.07], [35.152, 129.071]],
}

export const response: RouteSearchResponse = {
  request_id: 'req-1',
  profile: 'wheelchair',
  departure_at: '2026-08-03T13:00:00+09:00',
  prefer_shade: false,
  weather: { source: 'open_meteo', observed_at: null, forecast_for: '2026-08-03T13:00:00+09:00', temp_c: 31, feels_like_c: 34.2, precipitation_mm: 0, wind_ms: 3, pm10: 40, sky: 'clear', flags: ['heatwave', 'heat'], note: '' },
  routes: [walkRoute, { ...walkRoute, id: 'route_2', rank: 2, badges: ['shortest_walk'], cautions: [], transfers: 1 }],
  personalized: false,
  metadata: { profile: 'wheelchair', profile_label: '휠체어 이용자', weather_flags: ['heatwave', 'heat'], departure_at: null, preferences: { avoid_slope: true, prefer_shade: false }, shade_status: 'computed', shade_note: '', building_height_coverage: 0.97, elevation_resolution_m: 90, elapsed_ms: 130 },
}
