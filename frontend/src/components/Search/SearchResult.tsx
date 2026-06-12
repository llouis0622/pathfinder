import type { Place } from '../../types'

type Props = {
  results: Place[]
  onSelect: (place: Place) => void
}

// 장소 검색 결과 목록
export default function SearchResult({ results, onSelect }: Props) {
  return (
    <ul style={styles.list}>
      {results.map((place) => (
        <li key={place.id} style={styles.item} onMouseDown={() => onSelect(place)}>
          <span style={styles.name}>{place.name}</span>
          <span style={styles.address}>{place.address}</span>
        </li>
      ))}
    </ul>
  )
}

const styles: Record<string, React.CSSProperties> = {
  list: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: 6,
    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
    zIndex: 100,
    margin: 0,
    padding: 0,
    listStyle: 'none',
    maxHeight: 260,
    overflowY: 'auto',
  },
  item: {
    padding: '10px 14px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    borderBottom: '1px solid #f3f4f6',
  },
  name: { fontSize: 14, fontWeight: 600, color: '#111' },
  address: { fontSize: 12, color: '#6b7280' },
}
