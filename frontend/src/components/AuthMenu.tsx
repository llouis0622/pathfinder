import { useEffect, useRef, useState } from 'react'
import { fetchPreferences, resetPreferences } from '../api'
import type { AuthProviders, Preferences, User } from '../types'

type Props = {
  user: User | null
  providers: AuthProviders
  onLogin: (provider: 'kakao' | 'naver') => void
  onDevLogin: () => void
  onLogout: () => void
}

export default function AuthMenu({ user, providers, onLogin, onDevLogin, onLogout }: Props) {
  const [open, setOpen] = useState(false)
  const [prefs, setPrefs] = useState<Preferences | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  useEffect(() => {
    if (open && user) fetchPreferences().then(setPrefs).catch(() => setPrefs(null))
  }, [open, user])

  const canLogin = providers.providers.length > 0 || providers.dev_login

  return (
    <div className="auth" ref={ref}>
      {user ? (
        <button type="button" className="auth__user" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu">
          {user.avatar_url ? <img className="auth__avatar" src={user.avatar_url} alt="" /> : <span className="auth__avatar" aria-hidden="true">{user.nickname.slice(0, 1)}</span>}
          <span className="auth__name">{user.nickname}</span>
        </button>
      ) : (
        <button type="button" className="auth__login" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu" disabled={!canLogin}>
          로그인
        </button>
      )}
      {open && (
        <div className="auth__menu" role="menu">
          {user ? (
            <>
              <div className="auth__section">
                <div className="auth__title">내 취향</div>
                {prefs && prefs.updates > 0 ? (
                  <>
                    <ul className="auth__prefs">{prefs.summary.map((s) => <li key={s}>{s}</li>)}</ul>
                    <div className="auth__hint">경로 선택 {prefs.updates}회 학습</div>
                  </>
                ) : (
                  <div className="auth__hint">경로를 고를수록 취향을 배워요</div>
                )}
              </div>
              {prefs && prefs.updates > 0 && (
                <button type="button" role="menuitem" className="auth__item" onClick={async () => { await resetPreferences(); setPrefs({ updates: 0, weights: {}, summary: [] }) }}>
                  취향 초기화
                </button>
              )}
              <button type="button" role="menuitem" className="auth__item auth__item--danger" onClick={() => { setOpen(false); onLogout() }}>로그아웃</button>
            </>
          ) : (
            <>
              <div className="auth__section">
                <div className="auth__title">로그인하면 고른 경로를 기억해 다음 추천에 반영해요</div>
              </div>
              {providers.providers.includes('kakao') && (
                <button type="button" role="menuitem" className="auth__item auth__item--kakao" onClick={() => onLogin('kakao')}>
                  <span className="auth__brand" aria-hidden="true">K</span>카카오로 로그인
                </button>
              )}
              {providers.providers.includes('naver') && (
                <button type="button" role="menuitem" className="auth__item auth__item--naver" onClick={() => onLogin('naver')}>
                  <span className="auth__brand" aria-hidden="true">N</span>네이버로 로그인
                </button>
              )}
              {providers.dev_login && (
                <button type="button" role="menuitem" className="auth__item" onClick={() => { setOpen(false); onDevLogin() }}>데모 계정으로 로그인</button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
