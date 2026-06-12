// 경로 탐색 가중치 파라미터
export type RouteWeights = {
  avoid_stairs: boolean       // 계단 회피
  elevator_priority: boolean  // 엘리베이터 우선
  low_grade: boolean          // 낮은 경사 우선
  min_transfer: boolean       // 환승 최소화
  avoid_crowded: boolean      // 혼잡 회피
  wide_sidewalk: boolean      // 넓은 보도 우선
  shelter_nearby: boolean     // 쉼터 근접
  low_walk_distance: boolean  // 도보거리 최소화
  avoid_heat: boolean         // 폭염 회피
  avoid_cold: boolean         // 한파 회피
}

// 사용자 프로필
export type UserProfile = {
  id: string
  label: string
  weights: RouteWeights
}

// 좌표
export type Coordinate = {
  lat: number
  lng: number
}

// 장소 정보
export type Place = {
  id: string
  name: string
  address: string
  lat: number
  lng: number
  category: string
}

// 경로 요청 페이로드
export type RouteRequest = {
  origin: Coordinate & { name: string }
  destination: Coordinate & { name: string }
  profile: string
  weights: RouteWeights
}

// 경로 결과 단건
export type RouteResult = {
  id: string
  label: string
  duration_min: number
  distance_m: number
  path: Coordinate[]
  profile: string
  weights_applied: RouteWeights
  algorithm: string
}

// 경로 응답
export type RouteResponse = {
  routes: RouteResult[]
}

// 장소 검색 응답
export type PlaceResponse = {
  places: Place[]
}

// 선택된 지점 (출발지/도착지)
export type SelectedPoint = {
  place: Place
  type: 'origin' | 'destination'
}
