import { useState } from 'react'
import KakaoMap from '../components/Map/KakaoMap'
import SearchBar from '../components/Search/SearchBar'
import ProfileSelector, { USER_PROFILES } from '../components/Profile/ProfileSelector'
import RoutePanel from '../components/Route/RoutePanel'
import { useRoute } from '../hooks/useRoute'
import type { Place, RouteResult, UserProfile } from '../types'

// 메인 페이지 — 지도 + 검색 + 프로필 + 경로 결과
export default function MainPage() {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [selectedProfile, setSelectedProfile] = useState<UserProfile>(USER_PROFILES[0])
  const [selectedRoute, setSelectedRoute] = useState<RouteResult | null>(null)

  const { routes, loading, error, search, clear } = useRoute()

  // 경로 탐색 실행
  async function handleSearch() {
    if (!origin || !destination) return
    setSelectedRoute(null)
    await search(origin, destination, selectedProfile.id, selectedProfile.weights)
  }

  // 프로필 변경 시 기존 경로 초기화
  function handleProfileSelect(profile: UserProfile) {
    setSelectedProfile(profile)
    clear()
    setSelectedRoute(null)
  }

  const activePath = selectedRoute?.path ?? routes[0]?.path ?? []

  return (
    <div style={styles.page}>
      {/* 상단 검색바 */}
      <header style={styles.header}>
        <div style={styles.logo}>Pathfinder</div>
        <SearchBar
          placeholder="출발지 검색"
          selectedName={origin?.name ?? ''}
          onSelect={(place) => { setOrigin(place); clear(); setSelectedRoute(null) }}
        />
        <SearchBar
          placeholder="도착지 검색"
          selectedName={destination?.name ?? ''}
          onSelect={(place) => { setDestination(place); clear(); setSelectedRoute(null) }}
        />
        <button
          style={{
            ...styles.searchBtn,
            ...((!origin || !destination) ? styles.searchBtnDisabled : {}),
          }}
          onClick={handleSearch}
          disabled={!origin || !destination}
        >
          길찾기
        </button>
      </header>

      {/* 프로필 선택 */}
      <ProfileSelector selectedId={selectedProfile.id} onSelect={handleProfileSelect} />

      {/* 지도 */}
      <KakaoMap origin={origin} destination={destination} routePath={activePath} />

      {/* 경로 결과 패널 */}
      <RoutePanel
        routes={routes}
        selectedId={selectedRoute?.id ?? null}
        onSelect={(r) => setSelectedRoute(r)}
        loading={loading}
        error={error}
      />
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    fontFamily: "'Pretendard', 'Apple SD Gothic Neo', sans-serif",
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 16px',
    background: '#fff',
    borderBottom: '1px solid #e5e7eb',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    zIndex: 10,
  },
  logo: {
    fontWeight: 800,
    fontSize: 18,
    color: '#2563eb',
    whiteSpace: 'nowrap',
    marginRight: 8,
  },
  searchBtn: {
    padding: '8px 18px',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  searchBtnDisabled: {
    background: '#93c5fd',
    cursor: 'not-allowed',
  },
}
