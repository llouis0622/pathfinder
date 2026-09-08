import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, chooseRoute, fetchProfiles, fetchStoredRoute, searchRoutes } from './api'
import A11yMenu from './components/A11yMenu'
import AuthMenu from './components/AuthMenu'
import MapView, { type LocatedPoint } from './components/MapView'
import Onboarding from './components/Onboarding'
import ProfileChips from './components/ProfileChips'
import QuickPlaces from './components/QuickPlaces'
import ReportDialog, { type ReportTarget } from './components/ReportDialog'
import RouteDetail from './components/RouteDetail'
import RouteRow from './components/RouteRow'
import SearchBar from './components/SearchBar'
import { useAuth } from './hooks/useAuth'
import { resultsSpeech, routeSpeech, speak, stopSpeaking, useA11y } from './lib/a11y'
import { PROFILE_FALLBACK, PROFILE_SHORT, weatherLine } from './lib/format'
import { localRecent, onboarding, toPlace } from './lib/storage'
import type { MapInset, MapOverlay, Place, Profile, ProfileId, RouteSearchResponse } from './types'

type View = 'search' | 'list' | 'detail'

const ZERO_INSET: MapInset = { top: 0, right: 0, bottom: 0, left: 0 }

/** 오늘(KST) 의 hour(소수 허용) 시각을 ISO 문자열로. */
function kstToday(hour: number): string {
  const now = new Date()
  const kst = new Date(now.getTime() + 9 * 3600 * 1000)
  const y = kst.getUTCFullYear(), m = String(kst.getUTCMonth() + 1).padStart(2, '0'), d = String(kst.getUTCDate()).padStart(2, '0')
  const h = Math.floor(hour), mi = Math.round((hour - h) * 60)
  return `${y}-${m}-${d}T${String(h).padStart(2, '0')}:${String(mi).padStart(2, '0')}:00+09:00`
}
function currentHour(): number {
  const kst = new Date(Date.now() + 9 * 3600 * 1000)
  return Math.min(20, Math.max(6, Math.round((kst.getUTCHours() + kst.getUTCMinutes() / 60) * 2) / 2))
}
function formatHour(hour: number): string {
  const h = Math.floor(hour), mi = Math.round((hour - h) * 60)
  return `${h}:${String(mi).padStart(2, '0')}`
}
const MOBILE_QUERY = '(max-width: 860px)'
const NO_ROUTES: RouteSearchResponse['routes'] = []   // 매 렌더마다 새 [] 를 만들면 지도가 계속 다시 맞춘다

/** 공유 링크(/r/:id)로 열었을 때는 저장된 결과를 그대로 보여 준다. */
export default function App({ sharedRequestId }: { sharedRequestId?: string } = {}) {
  const auth = useAuth()
  const [a11y, setA11y] = useA11y()
  const [profiles, setProfiles] = useState<Profile[]>(PROFILE_FALLBACK)
  const [profile, setProfile] = useState<ProfileId>('wheelchair')
  const [preferShade, setPreferShade] = useState(false)
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [result, setResult] = useState<RouteSearchResponse | null>(null)
  const [noRoute, setNoRoute] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>('search')
  const [overlay, setOverlay] = useState<MapOverlay>('mode')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [choosing, setChoosing] = useState(false)
  const [chosenId, setChosenId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [announce, setAnnounce] = useState('')
  const [speaking, setSpeaking] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(true)
  const [inset, setInset] = useState<MapInset>(ZERO_INSET)
  const [myLocation, setMyLocation] = useState<LocatedPoint | null>(null)
  const [zoom, setZoom] = useState(12)
  const [shadeHour, setShadeHour] = useState<number | null>(null)   // null = 출발 시각(또는 지금)
  const [report, setReport] = useState<ReportTarget | null>(null)
  const [showGuide, setShowGuide] = useState(() => !sharedRequestId && !onboarding.seen())
  const [quickKey, setQuickKey] = useState(0)
  const [autoSearch, setAutoSearch] = useState(false)
  const keepResultRef = useRef(false)   // 공유 결과를 불러오며 출발·도착을 바꿀 때 결과가 지워지지 않게
  const dockRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  const sheetRef = useRef<HTMLElement>(null)
  const rowsRef = useRef<HTMLDivElement>(null)

  // 패널·시트가 지도를 얼마나 덮는지 재서, 지도가 '보이는 창' 안에 경로를 맞추게 한다
  useEffect(() => {
    const measure = () => {
      const mobile = window.matchMedia(MOBILE_QUERY).matches
      const panel = panelRef.current?.getBoundingClientRect()
      const sheet = sheetRef.current?.getBoundingClientRect()
      const dock = dockRef.current?.getBoundingClientRect()
      const next: MapInset = mobile
        ? { top: panel && panel.height > 0 ? Math.round(panel.bottom) : 0, right: 0, bottom: sheet ? Math.max(0, Math.round(window.innerHeight - sheet.top)) : 0, left: 0 }
        : { top: 0, right: 0, bottom: 0, left: dock ? Math.round(dock.right) : 0 }
      setInset((prev) => (prev.top === next.top && prev.right === next.right && prev.bottom === next.bottom && prev.left === next.left ? prev : next))
    }
    measure()
    window.addEventListener('resize', measure)
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    ;[panelRef.current, sheetRef.current, dockRef.current].forEach((el) => el && ro?.observe(el))
    // 바텀시트 높이 전환(.2s) 이 끝난 뒤 값으로 한 번 더 맞춘다
    const t = window.setTimeout(measure, 260)
    return () => { window.removeEventListener('resize', measure); ro?.disconnect(); window.clearTimeout(t) }
  }, [result, noRoute, view, sheetOpen])

  useEffect(() => {
    fetchProfiles().then((list) => list.length && setProfiles(list)).catch(() => undefined)
  }, [])

  // 공유 링크: 저장된 결과를 불러와 그대로 보여 준다
  useEffect(() => {
    if (!sharedRequestId) return
    let alive = true
    setLoading(true)
    fetchStoredRoute(sharedRequestId).then((s) => {
      if (!alive) return
      keepResultRef.current = true
      setOrigin(toPlace(s.origin, 'shared-o'))
      setDestination(toPlace(s.destination, 'shared-d'))
      setProfile(s.profile)
      if (s.routes.length === 0) { setNoRoute(true); setView('list'); return }
      setResult({ request_id: s.request_id, profile: s.profile, departure_at: s.created_at, prefer_shade: false, weather: s.weather ?? ({} as RouteSearchResponse['weather']), routes: s.routes,
        metadata: s.metadata ?? ({} as RouteSearchResponse['metadata']), personalized: false })
      setSelectedId(s.routes[0]?.id ?? null)
      setView('list')
      setAnnounce(`공유된 경로예요. ${resultsSpeech(s.routes.length, s.routes[0] ?? null)}`)
    }).catch((e) => {
      if (!alive) return
      setError(e instanceof ApiError && e.status === 404 ? '공유된 경로를 찾을 수 없어요. 링크가 만료됐을 수 있어요.' : '공유된 경로를 불러오지 못했어요.')
    }).finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [sharedRequestId])

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 2600)
    return () => window.clearTimeout(t)
  }, [toast])

  // 음성 안내를 끄면 읽던 것도 멈춘다
  useEffect(() => { if (!a11y.voice) { stopSpeaking(); setSpeaking(false) } }, [a11y.voice])
  useEffect(() => () => stopSpeaking(), [])

  const say = useCallback((text: string) => {
    setAnnounce(text)
    if (a11y.voice) speak(text)
  }, [a11y.voice])

  const selected = useMemo(() => result?.routes.find((r) => r.id === selectedId) ?? result?.routes[0] ?? null, [result, selectedId])
  const canSearch = !!origin && !!destination && !loading

  const runSearch = useCallback(async () => {
    if (!origin || !destination) return
    setLoading(true)
    setError(null)
    setNoRoute(false)
    stopSpeaking(); setSpeaking(false)
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
      setSheetOpen(true)
      if (res.routes.length === 0) { setResult(null); setNoRoute(true); say('경로를 찾지 못했어요. 다른 이용자 유형으로 다시 찾거나 출발지와 도착지를 바꿔 보세요.') }
      else say(resultsSpeech(res.routes.length, res.routes[0]))
      if (!auth.user) localRecent.push(origin, destination, profile)
      setQuickKey((k) => k + 1)
    } catch (e) {
      setResult(null)
      if (e instanceof ApiError && e.status === 422) {
        setNoRoute(true)
        setView('list')
        setSheetOpen(true)
        say('경로를 찾지 못했어요. 다른 이용자 유형으로 다시 찾거나 출발지와 도착지를 바꿔 보세요.')
      } else {
        const msg = e instanceof ApiError ? e.message : '경로를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.'
        setError(msg)
        say(msg)
      }
    } finally {
      setLoading(false)
    }
  }, [origin, destination, profile, preferShade, auth.user, say])

  async function choose() {
    if (!result || !selected) return
    setChoosing(true)
    try {
      const res = await chooseRoute(result.request_id, selected.id)
      setChosenId(selected.id)
      if (res.learned) setToast(res.summary[0] ? `취향에 반영했어요 · ${res.summary[0]}` : '취향에 반영했어요')
      else if (!auth.user) setToast('로그인하면 다음부터 이 취향을 기억해요')
      setAnnounce('이 경로로 안내를 시작해요')
    } catch {
      setToast('기록하지 못했어요')
    } finally {
      setChoosing(false)
    }
  }

  useEffect(() => {
    if (keepResultRef.current) { keepResultRef.current = false; return }
    setResult(null)
    setNoRoute(false)
    setChosenId(null)
    setView('search')
    stopSpeaking(); setSpeaking(false)
  }, [origin, destination, profile, preferShade])

  // '다른 유형으로 보기'·'출발·도착 바꾸기' 뒤에 자동으로 다시 찾는다
  useEffect(() => {
    if (!autoSearch) return
    setAutoSearch(false)
    if (origin && destination) void runSearch()
  }, [autoSearch, origin, destination, runSearch])

  const swap = () => {
    setOrigin(destination)
    setDestination(origin)
  }
  const retryWith = (p: ProfileId) => { setProfile(p); setAutoSearch(true) }
  const retrySwapped = () => { swap(); setAutoSearch(true) }

  const toggleSpeak = () => {
    if (speaking) { stopSpeaking(); setSpeaking(false); return }
    if (!selected) return
    const ok = speak(routeSpeech(selected, origin?.name ?? '', destination?.name ?? ''), { onEnd: () => setSpeaking(false) })
    if (ok) setSpeaking(true)
    else setToast('이 브라우저는 음성 읽기를 지원하지 않아요')
  }

  const share = async () => {
    if (!result) return
    const url = `${window.location.origin}/r/${result.request_id}`
    const title = `${origin?.name || '출발'} → ${destination?.name || '도착'} 편한 길`
    try {
      if (typeof navigator.share === 'function') { await navigator.share({ title, url }); return }
      await navigator.clipboard.writeText(url)
      setToast('링크를 복사했어요')
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return
      setToast(url)
    }
  }

  const onRowsKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!result || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return
    e.preventDefault()
    const ids = result.routes.map((r) => r.id)
    const cur = Math.max(0, ids.indexOf(selected?.id ?? ''))
    const next = e.key === 'ArrowDown' ? Math.min(ids.length - 1, cur + 1) : Math.max(0, cur - 1)
    setSelectedId(ids[next])
    const el = rowsRef.current?.children[next] as HTMLElement | undefined
    el?.focus()
    const r = result.routes[next]
    if (r) setAnnounce(`${next + 1}번 경로, ${Math.round(r.total_duration_min)}분`)
  }

  const closeGuide = () => { onboarding.dismiss(); setShowGuide(false) }
  const weather = result ? weatherLine(result.weather) : null
  const shadeAt = useMemo(() => (shadeHour === null ? result?.departure_at ?? null : kstToday(shadeHour)), [shadeHour, result?.departure_at])
  const hasSheet = !!result || noRoute

  return (
    <div className={`app app--${view}${hasSheet && !sheetOpen ? ' app--sheet-closed' : ''}`}>
      <div className="sr-only" aria-live="polite" aria-atomic="true">{announce}</div>
      <main className="map">
        <MapView origin={origin} destination={destination} routes={result?.routes ?? NO_ROUTES} selectedId={selected?.id ?? null} overlay={overlay} inset={inset}
          departureAt={shadeAt} onSelect={setSelectedId} onLocate={setMyLocation} onZoom={setZoom} />
        <div className="map__tools" role="radiogroup" aria-label="지도 표시">
          {([['mode', '기본'], ['grade', '경사'], ['shade', '그늘'], ['facility', '시설']] as [MapOverlay, string][]).map(([k, label]) => (
            <button key={k} type="button" role="radio" aria-checked={overlay === k} className={`map__tool${overlay === k ? ' is-on' : ''}`} onClick={() => setOverlay(k)}>{label}</button>
          ))}
        </div>
        {overlay === 'shade' && (
          <div className="map__shade" role="group" aria-label="그늘 시각">
            <label>
              <span>그늘 시각 <b>{shadeHour === null ? (result?.departure_at ? '출발 시각' : '지금') : formatHour(shadeHour)}</b></span>
              <input type="range" min={6} max={20} step={0.5} value={shadeHour ?? currentHour()} onChange={(e) => setShadeHour(Number(e.target.value))} aria-label="그늘을 볼 시각" />
            </label>
            {shadeHour !== null && <button type="button" className="map__shade-reset" onClick={() => setShadeHour(null)}>지금으로</button>}
          </div>
        )}
        {overlay !== 'mode' && zoom < 15 && <div className="map__hint">지도를 확대하면 {overlay === 'grade' ? '경사' : overlay === 'shade' ? '그늘' : '시설'}이 표시돼요</div>}
        {myLocation && origin?.id !== 'current' && (
          <button type="button" className="map__locate" onClick={() => setOrigin({ id: 'current', name: '현재 위치', address: '', lat: myLocation.lat, lng: myLocation.lng, category: '', source: 'geolocation' })}>
            내 위치에서 출발
          </button>
        )}
      </main>

      <div ref={dockRef} className={`dock dock--${view}`}>
        <aside ref={panelRef} className="panel" aria-label="길찾기">
          <div className="topbar">
            <span className="brand">Pathfinder</span>
            <div className="topbar__right">
              <button type="button" className="topbar__help" onClick={() => setShowGuide(true)} aria-label="도움말">?</button>
              <A11yMenu settings={a11y} onChange={setA11y} />
              <AuthMenu user={auth.user} providers={auth.providers} onLogin={auth.login} onDevLogin={auth.loginDev} onLogout={auth.logout} />
            </div>
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
              {view === 'search' && (
                <QuickPlaces user={auth.user} origin={origin} destination={destination} refreshKey={quickKey}
                  onPick={(o, d, p) => { setOrigin(o); setDestination(d); if (p && profiles.some((x) => x.id === p)) setProfile(p) }} />
              )}
              <ProfileChips profiles={profiles} selected={profile} onSelect={setProfile} preferShade={preferShade} onToggleShade={() => setPreferShade((v) => !v)} />
              {view === 'search' && (
                <button type="button" className="cta" onClick={runSearch} disabled={!canSearch}>
                  {loading ? '편한 길을 찾고 있어요…' : '길찾기'}
                </button>
              )}
              {error && <p className="error" role="alert">{error}</p>}
            </header>
          )}
        </aside>

        {hasSheet && (
          <section ref={sheetRef} className={`sheet${sheetOpen ? ' is-open' : ''}`} aria-label="추천 경로">
            <button type="button" className="sheet__handle" onClick={() => setSheetOpen((v) => !v)} aria-label={sheetOpen ? '경로 목록 접기' : '경로 목록 펼치기'} aria-expanded={sheetOpen}>
              <span />
            </button>
            <div className="sheet__scroll">
              {noRoute && !result && (
                <div className="noroute" role="status">
                  <h2 className="results__title">경로를 찾지 못했어요</h2>
                  <p className="noroute__text">
                    {PROFILE_SHORT[profile] ?? profile} 기준으로는 계단·급경사 없이 이어지는 길이 없었어요. 이렇게 해 보세요.
                  </p>
                  <div className="noroute__actions">
                    {profiles.filter((p) => p.id !== profile).map((p) => (
                      <button key={p.id} type="button" className="chip" onClick={() => retryWith(p.id)}>{PROFILE_SHORT[p.id] ?? p.label} 기준으로 보기</button>
                    ))}
                    <button type="button" className="chip" onClick={retrySwapped}>출발·도착 바꿔서 찾기</button>
                  </div>
                  <ul className="noroute__tips">
                    <li>출발지·도착지를 큰길이나 지하철역 가까이로 옮겨 보세요.</li>
                    <li>지도에서 <b>시설</b>을 켜면 주변 엘리베이터 위치를 볼 수 있어요.</li>
                    <li>실제로는 갈 수 있는 길이라면 <button type="button" className="noroute__link" onClick={() => origin && setReport({ lat: origin.lat, lng: origin.lng, placeName: origin.name, defaultKind: 'ok' })}>정보 정정을 제보</button>해 주세요.</li>
                  </ul>
                </div>
              )}
              {result && view === 'list' && (
                <>
                  <div className="results__head">
                    <h2 className="results__title">추천 경로{result.personalized && <span className="results__tag">내 취향 반영</span>}{sharedRequestId && <span className="results__tag">공유됨</span>}</h2>
                    {weather && <span className="results__weather">{weather}</span>}
                  </div>
                  <div ref={rowsRef} className="rows" role="listbox" aria-label="경로 목록. 위아래 화살표로 고르고 Enter 로 자세히 봐요" onKeyDown={onRowsKey}>
                    {result.routes.map((r) => (
                      <RouteRow key={r.id} route={r} selected={selected?.id === r.id}
                        onSelect={() => { setSelectedId(r.id); setSheetOpen(true); if (selected?.id === r.id) setView('detail') }} />
                    ))}
                  </div>
                  {selected && (
                    <div className="results__actions">
                      <button type="button" className="cta cta--ghost" onClick={() => setView('detail')}>경로 자세히 보기</button>
                      <button type="button" className="cta cta--ghost cta--icon" onClick={share} aria-label="경로 공유">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg>
                      </button>
                    </div>
                  )}
                </>
              )}
              {result && selected && view === 'detail' && (
                <RouteDetail route={selected} originName={origin?.name ?? ''} destinationName={destination?.name ?? ''} onBack={() => { setView('list'); stopSpeaking(); setSpeaking(false) }}
                  onChoose={choose} choosing={choosing} chosen={chosenId === selected.id}
                  onSpeak={toggleSpeak} speaking={speaking} onShare={share}
                  onReport={(t) => setReport({ ...t, requestId: result.request_id })} />
              )}
            </div>
          </section>
        )}
      </div>

      {report && <ReportDialog target={report} onClose={() => setReport(null)} onDone={(msg) => { setToast(msg); setAnnounce(msg) }} />}
      {showGuide && (
        <div className="modal" role="presentation" onClick={closeGuide}>
          <div className="modal__box" onClick={(e) => e.stopPropagation()}><Onboarding onClose={closeGuide} /></div>
        </div>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  )
}
