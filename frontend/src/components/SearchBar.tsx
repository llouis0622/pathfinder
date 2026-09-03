import { useEffect, useId, useRef, useState } from 'react'
import { searchPlaces } from '../api'
import type { Place } from '../types'

type Props = {
  kind: 'origin' | 'destination'
  placeholder: string
  value: Place | null
  near?: { lat: number; lng: number } | null
  onSelect: (place: Place | null) => void
  allowCurrentLocation?: boolean
}

export default function SearchBar({ kind, placeholder, value, near, onSelect, allowCurrentLocation }: Props) {
  const [query, setQuery] = useState(value?.name ?? '')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const listId = useId()
  const timer = useRef<number | null>(null)

  useEffect(() => {
    setQuery(value?.name ?? '')
  }, [value])

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current)
    const q = query.trim()
    if (!q || (value && q === value.name)) {
      setResults([])
      return
    }
    timer.current = window.setTimeout(async () => {
      try {
        const res = await searchPlaces(q, near ?? undefined)
        setResults(res.places)
        setOpen(true)
        setActive(-1)
      } catch {
        setResults([])
      }
    }, 250)
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
    <div className={`search search--${kind}`}>
      <span className="search__dot" aria-hidden="true" />
      <input
        className="search__input"
        type="text"
        role="combobox"
        aria-label={kind === 'origin' ? '출발지' : '도착지'}
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
      {allowCurrentLocation && !value && (
        <button type="button" className="search__loc" onClick={useCurrentLocation} aria-label="현재 위치 사용">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /><circle cx="12" cy="12" r="8" /></svg>
        </button>
      )}
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
