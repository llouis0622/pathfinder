import type { RouteResult } from '../../types'

type Props = {
  route: RouteResult
  isSelected: boolean
  onSelect: () => void
}

// 경로 결과 카드 단건
export default function RouteCard({ route, isSelected, onSelect }: Props) {
  const km = (route.distance_m / 1000).toFixed(1)

  return (
    <div
      style={{ ...styles.card, ...(isSelected ? styles.cardSelected : {}) }}
      onClick={onSelect}
    >
      <div style={styles.label}>{route.label}</div>
      <div style={styles.meta}>
        <span>{route.duration_min}분</span>
        <span style={styles.dot}>·</span>
        <span>{km}km</span>
        <span style={styles.dot}>·</span>
        <span style={styles.algo}>{route.algorithm.toUpperCase()}</span>
      </div>
      <div style={styles.profile}>프로필: {route.profile}</div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    padding: '10px 14px',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    cursor: 'pointer',
    background: '#fff',
    minWidth: 180,
  },
  cardSelected: {
    border: '2px solid #2563eb',
    background: '#eff6ff',
  },
  label: { fontWeight: 700, fontSize: 14, marginBottom: 4 },
  meta: { display: 'flex', gap: 4, fontSize: 13, color: '#374151', marginBottom: 2 },
  dot: { color: '#9ca3af' },
  algo: { color: '#6b7280', fontSize: 11 },
  profile: { fontSize: 11, color: '#9ca3af' },
}
