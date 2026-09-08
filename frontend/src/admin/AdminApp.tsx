import { useEffect, useState, type FormEvent } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import './admin.css'
import { adminLogin, adminLogout, adminMe, type AdminMe } from './api'
import { Analytics } from './pages/Analytics'
import Dashboard from './pages/Dashboard'
import { AccessLog, ChoicesLog, EngineLog, PlacesLog, RequestsLog } from './pages/Logs'
import { AlertsPage, DataQualityPage, ReportsPage } from './pages/Ops'
import PreferencesPage from './pages/Preferences'
import RequestDetailPage from './pages/RequestDetail'
import { UserDetailPage, UsersPage } from './pages/Users'

const NAV: { group: string; items: { to: string; label: string; end?: boolean }[] }[] = [
  { group: '개요', items: [{ to: '/admin', label: '대시보드', end: true }] },
  { group: '로그', items: [
    { to: '/admin/logs/requests', label: '경로 요청' }, { to: '/admin/logs/access', label: '접근·인증' },
    { to: '/admin/logs/engine', label: '엔진 성능' }, { to: '/admin/logs/choices', label: '경로 선택' }, { to: '/admin/logs/places', label: '장소 검색' },
  ] },
  { group: '사용자', items: [{ to: '/admin/users', label: '사용자' }, { to: '/admin/preferences', label: '취향 분포' }] },
  { group: '분석', items: [
    { to: '/admin/analytics/usage', label: '이용 추이' }, { to: '/admin/analytics/quality', label: '경로 품질' }, { to: '/admin/analytics/spatial', label: '공간 분석' },
  ] },
  { group: '운영', items: [{ to: '/admin/data-quality', label: '데이터 품질' }, { to: '/admin/reports', label: '제보 검토' }, { to: '/admin/alerts', label: '알림·한도' }] },
]

const TITLES: [RegExp, string][] = [
  [/^\/admin\/?$/, '대시보드'], [/^\/admin\/logs\/requests\/.+/, '경로 요청 상세'], [/^\/admin\/logs\/requests/, '경로 요청 로그'],
  [/^\/admin\/logs\/access/, '접근·인증 로그'], [/^\/admin\/logs\/engine/, '엔진 성능 로그'], [/^\/admin\/logs\/choices/, '경로 선택 로그'],
  [/^\/admin\/logs\/places/, '장소 검색 로그'], [/^\/admin\/users\/.+/, '사용자 상세'], [/^\/admin\/users/, '사용자'],
  [/^\/admin\/preferences/, '취향 분포'], [/^\/admin\/analytics\/usage/, '이용 추이'], [/^\/admin\/analytics\/quality/, '경로 품질'],
  [/^\/admin\/analytics\/spatial/, '공간 분석'], [/^\/admin\/data-quality/, '데이터 품질'], [/^\/admin\/reports/, '제보 검토·오버라이드'], [/^\/admin\/alerts/, '알림·요청 한도'],
]

export default function AdminApp() {
  const [me, setMe] = useState<AdminMe | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    adminMe().then(setMe).catch(() => setError('관리자 API 에 연결하지 못했어요'))
  }, [])

  if (error) return <div className="adm-login"><div className="adm-login__box"><h1>관리자</h1><p className="adm-error">{error}</p></div></div>
  if (!me) return <div className="adm-boot">확인 중…</div>
  if (!me.configured) {
    return (
      <div className="adm-login">
        <div className="adm-login__box">
          <h1>관리자 기능이 꺼져 있어요</h1>
          {me.reason === 'jwt_secret'
            ? <p>루트 <code>.env</code> 의 <code>JWT_SECRET</code> 이 자리표시자이거나 32자 미만이에요. 이 상태로는 관리자 세션을 누구나 위조할 수 있어 잠가 둡니다. <code>openssl rand -base64 48</code> 로 만든 값을 넣고 다시 시작하세요.</p>
            : <p>루트 <code>.env</code> 의 <code>ADMIN_PASSWORD</code> 를 설정하면 관리자 페이지가 열립니다.</p>}
          <Link className="adm-btn" to="/">서비스로 돌아가기</Link>
        </div>
      </div>
    )
  }
  if (!me.admin) return <Login onDone={() => setMe({ ...me, admin: true })} />
  return <Shell onLogout={async () => { await adminLogout().catch(() => undefined); setMe({ ...me, admin: false }) }} />
}

function Login({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await adminLogin(password)
      onDone()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : '로그인하지 못했어요')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="adm-login">
      <form className="adm-login__box" onSubmit={submit}>
        <h1>Pathfinder 관리자</h1>
        <p>관리자 비밀번호를 입력하세요.</p>
        <input type="password" autoFocus autoComplete="current-password" placeholder="비밀번호" value={password} onChange={(e) => setPassword(e.target.value)} aria-label="관리자 비밀번호" />
        {msg && <div className="adm-error" role="alert">{msg}</div>}
        <button type="submit" className="adm-btn adm-btn--primary" disabled={!password || busy}>{busy ? '확인 중…' : '로그인'}</button>
        <Link className="adm-btn adm-btn--ghost" to="/">서비스로 돌아가기</Link>
      </form>
    </div>
  )
}

function Shell({ onLogout }: { onLogout: () => void }) {
  const { pathname } = useLocation()
  const title = TITLES.find(([re]) => re.test(pathname))?.[1] ?? '관리자'
  useEffect(() => { document.title = `${title} · Pathfinder 관리자` }, [title])
  return (
    <div className="adm">
      <aside className="adm__side">
        <div className="adm__brand"><b>Pathfinder</b><span>관리자</span></div>
        <nav className="adm__nav" aria-label="관리자 메뉴">
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="adm__group">{g.group}</div>
              {g.items.map((it) => <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => (isActive ? 'is-on' : '')}>{it.label}</NavLink>)}
            </div>
          ))}
        </nav>
      </aside>
      <div className="adm__main">
        <header className="adm__top">
          <h1>{title}</h1>
          <div className="adm__top-actions">
            <Link className="adm-btn adm-btn--ghost" to="/">서비스 열기</Link>
            <button type="button" className="adm-btn" onClick={onLogout}>로그아웃</button>
          </div>
        </header>
        <main className="adm__body">
          <Routes>
            <Route index element={<Dashboard />} />
            <Route path="logs/requests" element={<RequestsLog />} />
            <Route path="logs/requests/:id" element={<RequestDetailPage />} />
            <Route path="logs/access" element={<AccessLog />} />
            <Route path="logs/engine" element={<EngineLog />} />
            <Route path="logs/choices" element={<ChoicesLog />} />
            <Route path="logs/places" element={<PlacesLog />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="users/:id" element={<UserDetailPage />} />
            <Route path="preferences" element={<PreferencesPage />} />
            <Route path="analytics/:tab" element={<Analytics />} />
            <Route path="data-quality" element={<DataQualityPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
