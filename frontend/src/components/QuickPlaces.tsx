import { useEffect, useState } from 'react'
import { addMyPlace, deleteMyPlace, fetchMyPlaces, fetchRecent } from '../api'
import { localFavorites, localRecent, toPlace, type Favorite, type Recent } from '../lib/storage'
import type { Place, ProfileId, User } from '../types'

type Props = {
  user: User | null
  origin: Place | null
  destination: Place | null
  onPick: (origin: Place | null, destination: Place | null, profile?: ProfileId) => void
  refreshKey?: number
}

const LABELS = ['집', '직장', '병원', '자주 가는 곳']

/** 검색창 아래 즐겨찾기·최근 검색 칩. 게스트는 브라우저, 로그인 사용자는 서버에 저장한다. */
export default function QuickPlaces({ user, origin, destination, onPick, refreshKey = 0 }: Props) {
  const [favorites, setFavorites] = useState<Favorite[]>([])
  const [recent, setRecent] = useState<Recent[]>([])
  const [saving, setSaving] = useState<'origin' | 'destination' | null>(null)

  const load = async () => {
    if (user) {
      try {
        const [f, r] = await Promise.all([fetchMyPlaces(), fetchRecent()])
        setFavorites(f)
        setRecent(r)
        return
      } catch { /* 서버 실패 시 로컬로 */ }
    }
    setFavorites(localFavorites.list())
    setRecent(localRecent.list())
  }
  useEffect(() => { load() }, [user?.id, refreshKey])   // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (label: string, place: Place) => {
    if (user) {
      try { await addMyPlace({ label, name: place.name, address: place.address, lat: place.lat, lng: place.lng }) } catch { /* 무시 */ }
    } else {
      localFavorites.save(label, place)
    }
    setSaving(null)
    load()
  }
  const remove = async (f: Favorite) => {
    if (user) { try { await deleteMyPlace(f.id) } catch { /* 무시 */ } } else localFavorites.remove(f.id)
    load()
  }

  const target = saving === 'origin' ? origin : saving === 'destination' ? destination : null
  const hasAny = favorites.length > 0 || recent.length > 0
  const canSave = (origin && origin.id !== 'current') || destination

  if (!hasAny && !canSave) return null
  return (
    <div className="quick" aria-label="즐겨찾기와 최근 검색">
      {favorites.length > 0 && (
        <div className="quick__row">
          <span className="quick__label">즐겨찾기</span>
          {favorites.map((f) => (
            <span key={f.id} className="quick__chip">
              <button type="button" onClick={() => onPick(origin ?? null, toPlace(f, f.id))} title={`${f.name} (도착지로)`}>{f.label}</button>
              <button type="button" className="quick__x" aria-label={`${f.label} 즐겨찾기 삭제`} onClick={() => remove(f)}>×</button>
            </span>
          ))}
        </div>
      )}
      {recent.length > 0 && (
        <div className="quick__row">
          <span className="quick__label">최근</span>
          {recent.slice(0, 5).map((r, i) => (
            <button key={i} type="button" className="quick__chip quick__chip--recent" onClick={() => onPick(toPlace(r.origin, 'recent-o'), toPlace(r.destination, 'recent-d'), r.profile as ProfileId)}>
              {r.origin.name || '출발'} → {r.destination.name || '도착'}
            </button>
          ))}
        </div>
      )}
      {canSave && !saving && (
        <div className="quick__row">
          {origin && origin.id !== 'current' && <button type="button" className="quick__save" onClick={() => setSaving('origin')}>☆ 출발지 저장</button>}
          {destination && <button type="button" className="quick__save" onClick={() => setSaving('destination')}>☆ 도착지 저장</button>}
        </div>
      )}
      {saving && target && (
        <div className="quick__row" role="group" aria-label="즐겨찾기 이름">
          <span className="quick__label">{target.name}을(를)</span>
          {LABELS.map((l) => <button key={l} type="button" className="quick__chip" onClick={() => save(l, target)}>{l}</button>)}
          <button type="button" className="quick__x" aria-label="취소" onClick={() => setSaving(null)}>×</button>
        </div>
      )}
    </div>
  )
}
