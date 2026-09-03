/** 관리자 화면 공용 조각: 카드, 표, 페이지네이션, 필터, 상태 배지, 데이터 훅. */
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BADGE_LABELS, PROFILE_SHORT, WEATHER_FLAG_LABELS } from '../lib/format'
import type { UserRef } from './api'

export function useFetch<T>(load: () => Promise<T>, deps: unknown[]): { data: T | null; loading: boolean; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    load().then((d) => { if (alive) setData(d) }).catch((e) => { if (alive) setError(e instanceof Error ? e.message : '불러오지 못했어요') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { data, loading, error, reload: () => setTick((t) => t + 1) }
}

export const fmtDateTime = (iso: string | null | undefined) => {
  if (!iso) return '–'
  const d = new Date(iso)
  return d.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}
export const fmtDate = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', year: '2-digit', month: '2-digit', day: '2-digit' }) : '–')
export const profileLabel = (p: string) => (PROFILE_SHORT as Record<string, string>)[p] ?? p
export const badgeLabel = (b: string) => (BADGE_LABELS as Record<string, string>)[b] ?? b
export const flagLabel = (f: string) => (WEATHER_FLAG_LABELS as Record<string, string>)[f] ?? f
export const STATUS_LABEL: Record<string, string> = { ok: '성공', no_route: '경로 없음', error: '오류' }
export const KIND_LABEL: Record<string, string> = { api: 'API', auth: '인증', admin: '관리자' }
export const PROVIDER_LABEL: Record<string, string> = { kakao: '카카오', naver: '네이버', dev: '데모' }

export function Card({ title, children, actions, className }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`adm-card${className ? ` ${className}` : ''}`}>
      {(title || actions) && <header className="adm-card__head"><h2>{title}</h2>{actions && <div className="adm-card__actions">{actions}</div>}</header>}
      {children}
    </section>
  )
}

export function Status({ value }: { value: string }) {
  return <span className={`adm-status adm-status--${value}`}>{STATUS_LABEL[value] ?? value}</span>
}

export function HttpStatus({ code }: { code: number }) {
  const tone = code >= 500 ? 'error' : code >= 400 ? 'warn' : 'ok'
  return <span className={`adm-status adm-status--${tone}`}>{code}</span>
}

export function UserChip({ user, id }: { user: UserRef | null; id?: string | null }) {
  if (!user) return <span className="adm-muted">{id ? '삭제된 사용자' : '게스트'}</span>
  return (
    <Link className="adm-user" to={`/admin/users/${user.id}`}>
      {user.avatar_url ? <img src={user.avatar_url} alt="" /> : <i>{user.nickname.slice(0, 1)}</i>}
      <span>{user.nickname}</span>
      <small>{PROVIDER_LABEL[user.provider] ?? user.provider}</small>
    </Link>
  )
}

export function Pager({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (p: number) => void }) {
  return (
    <div className="adm-pager">
      <span className="adm-muted">총 {total.toLocaleString('ko-KR')}건 · {page}/{pages} 페이지</span>
      <div>
        <button type="button" className="adm-btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>이전</button>
        <button type="button" className="adm-btn" disabled={page >= pages} onClick={() => onPage(page + 1)}>다음</button>
      </div>
    </div>
  )
}

export function Filters({ children, onReset }: { children: ReactNode; onReset?: () => void }) {
  return (
    <div className="adm-filters">
      {children}
      {onReset && <button type="button" className="adm-btn adm-btn--ghost" onClick={onReset}>초기화</button>}
    </div>
  )
}

export function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string }) {
  return (
    <label className="adm-field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>{options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
    </label>
  )
}

export function Input({ value, onChange, label, type = 'text', placeholder }: { value: string; onChange: (v: string) => void; label: string; type?: string; placeholder?: string }) {
  return (
    <label className="adm-field">
      <span>{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}

export function DaysPicker({ value, onChange }: { value: number; onChange: (d: number) => void }) {
  return (
    <div className="adm-seg" role="radiogroup" aria-label="기간">
      {[7, 30, 90].map((d) => (
        <button key={d} type="button" role="radio" aria-checked={value === d} className={`adm-seg__btn${value === d ? ' is-on' : ''}`} onClick={() => onChange(d)}>{d}일</button>
      ))}
    </div>
  )
}

export function Loading({ error, loading, children }: { error: string | null; loading: boolean; children: ReactNode }) {
  if (error) return <div className="adm-error" role="alert">{error}</div>
  if (loading) return <div className="adm-empty">불러오는 중…</div>
  return <>{children}</>
}

export function Empty({ text = '아직 데이터가 없어요' }: { text?: string }) {
  return <div className="adm-empty">{text}</div>
}

export function Table({ head, children, className }: { head: ReactNode[]; children: ReactNode; className?: string }) {
  return (
    <div className="adm-scroll">
      <table className={`adm-table${className ? ` ${className}` : ''}`}>
        <thead><tr>{head.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Chips({ items, map }: { items: string[]; map?: (s: string) => string }) {
  if (!items.length) return <span className="adm-muted">–</span>
  return <span className="adm-chips">{items.map((b) => <i key={b}>{map ? map(b) : b}</i>)}</span>
}

export function Rank({ rank }: { rank: number | null | undefined }) {
  if (rank === null || rank === undefined) return <span className="adm-muted">–</span>
  return <span className={`adm-rank adm-rank--${rank}`}>{rank}순위</span>
}

export function Json({ value }: { value: unknown }) {
  return <details className="adm-json"><summary>원본 보기</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>
}
