import { useEffect, useMemo, useState } from 'react'
import { ApiError, fetchProfiles, searchRoutes } from './api'
import ConditionsPanel, { type Conditions } from './components/ConditionsPanel'
import MapView from './components/MapView'
import ProfileSelector from './components/ProfileSelector'
import RouteCard from './components/RouteCard'
import RouteDetail from './components/RouteDetail'
import SearchBar from './components/SearchBar'
import WeatherChip from './components/WeatherChip'
import { PROFILE_FALLBACK, localInputToIso, toLocalDatetimeInput } from './lib/format'
import type { MapOverlay, Place, Profile, ProfileId, RouteSearchResponse } from './types'

export default function App() {
  const [profiles, setProfiles] = useState<Profile[]>(PROFILE_FALLBACK)
  const [profile, setProfile] = useState<ProfileId>('wheelchair')
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [conditions, setConditions] = useState<Conditions>({ departure: toLocalDatetimeInput(new Date()), weatherMode: 'auto', manual: {} })
  const [result, setResult] = useState<RouteSearchResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [overlay, setOverlay] = useState<MapOverlay>('mode')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [panelOpen, setPanelOpen] = useState(true)

  useEffect(() => {
    fetchProfiles().then((list) => list.length && setProfiles(list)).catch(() => undefined)
  }, [])

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
        departure_at: localInputToIso(conditions.departure),
        weather_mode: conditions.weatherMode,
        manual_weather: conditions.weatherMode === 'manual' ? conditions.manual : undefined,
      })
      setResult(res)
      setSelectedId(res.routes[0]?.id ?? null)
      setPanelOpen(true)
    } catch (e) {
      setResult(null)
      setError(e instanceof ApiError ? e.message : '경로를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')
    } finally {
      setLoading(false)
    }
  }

  const swap = () => {
    setOrigin(destination)
    setDestination(origin)
  }

  return (
    <div className="app">
      <aside className={`panel${panelOpen ? '' : ' is-collapsed'}`} aria-label="경로 검색 패널">
        <header className="brand">
          <h1 className="brand__title">Pathfinder</h1>
          <p className="brand__sub">부산 교통약자 맞춤 경로 · 도보 + 지하철 + 버스</p>
          <button type="button" className="panel__toggle" aria-expanded={panelOpen} onClick={() => setPanelOpen((v) => !v)}>
            {panelOpen ? '지도 크게 보기' : '검색 패널 열기'}
          </button>
        </header>

        <section className="section">
          <SearchBar label="출발지" placeholder="역·정류장·장소 이름" value={origin} onSelect={setOrigin} allowCurrentLocation />
          <div className="swap-row">
            <button type="button" className="btn btn--ghost" onClick={swap} disabled={!origin && !destination} aria-label="출발지와 도착지 바꾸기">⇅ 바꾸기</button>
          </div>
          <SearchBar label="도착지" placeholder="역·정류장·장소 이름" value={destination} near={origin} onSelect={setDestination} />
        </section>

        <section className="section">
          <ProfileSelector profiles={profiles} selected={profile} onSelect={setProfile} />
        </section>

        <section className="section">
          <ConditionsPanel value={conditions} onChange={setConditions} />
        </section>

        <div className="section">
          <button type="button" className="btn btn--primary btn--block" onClick={runSearch} disabled={!canSearch}>
            {loading ? '경로 탐색 중… (ACO + GA)' : '길찾기'}
          </button>
          {error && <p className="error" role="alert">{error}</p>}
        </div>

        {result && (
          <>
            <section className="section">
              <WeatherChip weather={result.weather} metadata={result.metadata} />
            </section>
            <section className="section">
              <div className="section__head">
                <h2 className="section__title">추천 경로 {result.routes.length}개</h2>
                <div className="segmented segmented--small" role="radiogroup" aria-label="지도 표시">
                  {([['mode', '수단'], ['grade', '경사'], ['shade', '그늘']] as [MapOverlay, string][]).map(([k, label]) => (
                    <button key={k} type="button" role="radio" aria-checked={overlay === k} className={`segmented__item${overlay === k ? ' is-selected' : ''}`} onClick={() => setOverlay(k)}>{label}</button>
                  ))}
                </div>
              </div>
              <div className="cards" role="listbox" aria-label="추천 경로">
                {result.routes.map((r) => (
                  <RouteCard key={r.id} route={r} selected={selected?.id === r.id} onSelect={() => setSelectedId(r.id)}
                    shadeAvailable={result.metadata.shade_status === 'computed'} />
                ))}
              </div>
            </section>
            {selected && (
              <section className="section">
                <RouteDetail route={selected} />
              </section>
            )}
            <footer className="section footer">
              데이터: OpenStreetMap(ODbL), Copernicus DEM, 부산교통공사, 국토교통부. 경사는 90m 지형 추정치이며 보도 턱·역사 내부 경사는 반영되지 않습니다.
            </footer>
          </>
        )}
      </aside>

      <main className="map">
        <MapView origin={origin} destination={destination} routes={result?.routes ?? []} selectedId={selected?.id ?? null} overlay={overlay} onSelect={setSelectedId} />
        {result && overlay !== 'mode' && (
          <div className="legend" aria-label="범례">
            {overlay === 'grade' ? (
              <>
                <span><i style={{ background: '#22c55e' }} /> 0–3%</span>
                <span><i style={{ background: '#eab308' }} /> 3–6%</span>
                <span><i style={{ background: '#f97316' }} /> 6–10%</span>
                <span><i style={{ background: '#dc2626' }} /> 10%+</span>
              </>
            ) : (
              <>
                <span><i style={{ background: 'rgb(249, 115, 22)' }} /> 볕</span>
                <span><i style={{ background: 'rgb(30, 58, 138)' }} /> 그늘</span>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
