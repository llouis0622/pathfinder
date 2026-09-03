import { useCallback, useEffect, useState } from 'react'
import { devLogin, fetchAuthProviders, fetchMe, loginUrl, logout as apiLogout } from '../api'
import type { AuthProviders, User } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [providers, setProviders] = useState<AuthProviders>({ providers: [], dev_login: false })
  const [ready, setReady] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setUser(await fetchMe())
    } catch {
      setUser(null)
    } finally {
      setReady(true)
    }
  }, [])

  useEffect(() => {
    fetchAuthProviders().then(setProviders).catch(() => undefined)
    refresh()
    // OAuth 콜백에서 돌아온 경우 URL 정리
    const url = new URL(window.location.href)
    if (url.searchParams.has('login')) {
      url.searchParams.delete('login')
      window.history.replaceState({}, '', url.pathname + (url.search || '') + url.hash)
    }
  }, [refresh])

  const login = useCallback((provider: 'kakao' | 'naver') => {
    window.location.href = loginUrl(provider)
  }, [])

  const loginDev = useCallback(async () => {
    setUser(await devLogin())
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
  }, [])

  return { user, providers, ready, login, loginDev, logout, refresh }
}
