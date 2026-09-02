import { useEffect, useMemo, useState } from 'react'
import { ApiError, chooseRoute, fetchProfiles, searchRoutes } from './api'
import AuthMenu from './components/AuthMenu'
import MapView from './components/MapView'
import ProfileChips from './components/ProfileChips'
import RouteDetail from './components/RouteDetail'
import RouteRow from './components/RouteRow'
import SearchBar from './components/SearchBar'
import { useAuth } from './hooks/useAuth'
import { PROFILE_FALLBACK, weatherLine } from './lib/format'
import type { MapOverlay, Place, Profile, ProfileId, RouteSearchResponse } from './types'

type View = 'search' | 'list' | 'detail'

export default function App() {
  const auth = useAuth()
  const [profiles, setProfiles] = useState<Profile[]>(PROFILE_FALLBACK)
  const [profile, setProfile] = useState<ProfileId>('wheelchair')
  const [preferShade, setPreferShade] = useState(false)
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [result, setResult] = useState<RouteSearchResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>('search')
  const [overlay, setOverlay] = useState<MapOverlay>('mode')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [choosing, setChoosing] = useState(false)
  const [chosenId, setChosenId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    fetchProfiles().then((list) => list.length && setProfiles(list)).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 2600)
    return () => window.clearTimeout(t)
  }, [toast])

  const selected = useMemo(() => result?.routes.find((r) => r.id === selectedId) ?? result?.routes[0] ?? null, [result, selectedId])
  const canSearch = !!origin && !!destination && !loading

  async function runSearch() {
    if (!origin || !destination) return
    setLoading(true)
    setError(null)
    try {
      const res = await searchRoutes({
        origin: { lat: origin.lat, lng: origin.lng, name: origin.name },
        destination: { lat: destination.lat, lng: destination.lng, name: destination.name },
        profile,
        prefer_shade: preferShade,
      })
      setResult(res)
      setSelectedId(res.routes[0]?.id ?? null)
      setChosenId(null)
      setView('list')
    } catch (e) {
      setResult(null)
      setError(e instanceof ApiError ? e.message : '경로를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.')
    } finally {
      setLoading(false)
    }
  }

  async function choose() {
    if (!result || !selected) return
    setChoosing(true)
    try {
      const res = await chooseRoute(result.request_id, selected.id)
      setChosenId(selected.id)
      if (res.learned) setToast(res.summary[0] ? `취향에 반영했어요 · ${res.summary[0]}` : '취향에 반영했어요')
      else if (!auth.user) setToast('로그인하면 다음부터 이 취향을 기억해요')
    } catch {
      setToast('기록하지 못했어요')
    } finally {
      setChoosing(false)
    }
  }

  useEffect(() => {
    setResult(null)
    setChosenId(null)
    setView('search')
  }, [origin, destination, profile, preferShade])

  const swap = () => {
    setOrigin(destination)
    setDestination(origin)
  }
  const weather = result ? weatherLine(result.weather) : null

  return (
    <div className="app">
      <main className="map">
        <MapView origin={origin} destination={destination} routes={result?.routes ?? []} selectedId={selected?.id ?? null} overlay={overlay} onSelect={setSelectedId} />
        {result && (
          <div className="map__tools" role="radiogroup" aria-label="지도 표시">
            {([['mode', '기본'], ['grade', '경사'], ['shade', '그늘']] as [MapOverlay, string][]).map(([k, label]) => (
              <button key={k} type="button" role="radio" aria-checked={overlay === k} className={`map__tool${overlay === k ? ' is-on' : ''}`} onClick={() => setOverlay(k)}>{label}</button>
            ))}
          </div>
        )}
      </main>

      <aside className={`panel panel--${view}`} aria-label="길찾기">
        <div className="panel__scroll">
          <div className="topbar">
            <span className="brand">Pathfinder</span>
            <AuthMenu user={auth.user} providers={auth.providers} onLogin={auth.login} onDevLogin={auth.loginDev} onLogout={auth.logout} />
          </div>

          {view !== 'detail' && (
            <header className="head">
              <div className="inputs">
                <SearchBar kind="origin" placeholder="출발지" value={origin} onSelect={setOrigin} allowCurrentLocation />
                <div className="inputs__divider" />
                <SearchBar kind="destination" placeholder="도착지" value={destination} near={origin} onSelect={setDestination} />
                <button type="button" className="inputs__swap" onClick={swap} disabled={!origin && !destination} aria-label="출발지와 도착지 바꾸기">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3" /></svg>
                </button>
              </div>
              <ProfileChips profiles={profiles} selected={profile} onSelect={setProfile} preferShade={preferShade} onToggleShade={() => setPreferShade((v) => !v)} />
              {view === 'search' && (
                <button type="button" className="cta" onClick={runSearch} disabled={!canSearch}>
                  {loading ? '편한 길을 찾고 있어요…' : '길찾기'}
                </button>
              )}
              {error && <p className="error" role="alert">{error}</p>}
            </header>
          )}

          {result && view === 'list' && (
            <section className="results" aria-label="추천 경로">
              <div className="results__head">
                <h2 className="results__title">추천 경로{result.personalized && <span className="results__tag">내 취향 반영</span>}</h2>
                {weather && <span className="results__weather">{weather}</span>}
              </div>
              <div className="rows" role="listbox" aria-label="경로 목록">
                {result.routes.map((r) => (
                  <RouteRow key={r.id} route={r} selected={selected?.id === r.id}
                    onSelect={() => { setSelectedId(r.id); if (selected?.id === r.id) setView('detail') }} />
                ))}
              </div>
              {selected && (
                <button type="button" className="cta cta--ghost" onClick={() => setView('detail')}>경로 자세히 보기</button>
              )}
            </section>
          )}

          {result && selected && view === 'detail' && (
            <RouteDetail route={selected} originName={origin?.name ?? ''} destinationName={destination?.name ?? ''} onBack={() => setView('list')}
              onChoose={choose} choosing={choosing} chosen={chosenId === selected.id} />
          )}
        </div>
      </aside>

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  )
}
