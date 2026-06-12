import { useState } from 'react'
import { searchPlaces } from '../../api/place'
import type { Place } from '../../types'
import SearchResult from './SearchResult'

type Props = {
  placeholder: string
  onSelect: (place: Place) => void
  selectedName: string
}

// 장소 검색 입력창 컴포넌트
export default function SearchBar({ placeholder, onSelect, selectedName }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  async function handleSearch(value: string) {
    setQuery(value)
    if (!value.trim()) {
      setResults([])
      setOpen(false)
      return
    }
    setLoading(true)
    try {
      const res = await searchPlaces(value)
      setResults(res.places)
      setOpen(true)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(place: Place) {
    onSelect(place)
    setQuery('')
    setResults([])
    setOpen(false)
  }

  return (
    <div style={styles.wrapper}>
      <input
        style={styles.input}
        type="text"
        placeholder={selectedName || placeholder}
        value={query}
        onChange={(e) => handleSearch(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {loading && <span style={styles.loading}>검색 중...</span>}
      {open && results.length > 0 && (
        <SearchResult results={results} onSelect={handleSelect} />
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { position: 'relative', flex: 1 },
  input: {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #d1d5db',
    borderRadius: 6,
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
  },
  loading: { position: 'absolute', right: 10, top: 10, fontSize: 12, color: '#888' },
}
