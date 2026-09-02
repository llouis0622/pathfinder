import { useEffect, useId, useRef, useState } from 'react'
import { searchPlaces } from '../api'
import type { Place } from '../types'

type Props = {
  label: string
  placeholder: string
  value: Place | null
  near?: { lat: number; lng: number } | null
  onSelect: (place: Place | null) => void
  allowCurrentLocation?: boolean
}

export default function SearchBar({ label, placeholder, value, near, onSelect, allowCurrentLocation }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(-1)
  const listId = useId()
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current)
    const q = query.trim()
    if (!q || (value && q === value.name)) {
      setResults([])
      return
    }
    timer.current = window.setTimeout(async () => {
      setLoading(true)
      try {
        const res = await searchPlaces(q, near ?? undefined)
        setResults(res.places)
        setOpen(true)
        setActive(-1)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [query, near, value])

  const choose = (p: Place) => {
    onSelect(p)
    setQuery(p.name)
    setOpen(false)
  }

  const useCurrentLocation = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition((pos) => {
      choose({ id: 'current', name: '현재 위치', address: '', lat: pos.coords.latitude, lng: pos.coords.longitude, category: '', source: 'geolocation' })
    })
  }

  return (
    <div className="search">
      <label className="search__label">{label}</label>
      <div className="search__row">
        <input
          className="search__input"
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            if (value) onSelect(null)
          }}
          onFocus={() => results.length > 0 && setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (!open) return
            if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
            if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(results[active]) }
            if (e.key === 'Escape') setOpen(false)
          }}
        />
        {allowCurrentLocation && (
          <button type="button" className="btn btn--ghost" onClick={useCurrentLocation} title="현재 위치 사용" aria-label="현재 위치 사용">📍</button>
        )}
      </div>
      {loading && <span className="search__hint">검색 중…</span>}
      {value && <span className="search__hint">{value.address || value.category || value.source}</span>}
      {open && results.length > 0 && (
        <ul id={listId} className="search__list" role="listbox">
          {results.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === active} className={`search__item${i === active ? ' is-active' : ''}`}
              onMouseDown={() => choose(p)}>
              <span className="search__name">{p.name}</span>
              <span className="search__addr">{p.address || p.category}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
