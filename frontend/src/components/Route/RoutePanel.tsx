import type { RouteResult } from '../../types'
import RouteCard from './RouteCard'

type Props = {
  routes: RouteResult[]
  selectedId: string | null
  onSelect: (route: RouteResult) => void
  loading: boolean
  error: string | null
}

// 경로 결과 패널 (하단)
export default function RoutePanel({ routes, selectedId, onSelect, loading, error }: Props) {
  if (loading) {
    return <div style={styles.bar}><span style={styles.msg}>경로를 탐색 중입니다...</span></div>
  }
  if (error) {
    return <div style={styles.bar}><span style={{ ...styles.msg, color: '#dc2626' }}>{error}</span></div>
  }
  if (routes.length === 0) return null

  return (
    <div style={styles.bar}>
      {routes.map((r) => (
        <RouteCard
          key={r.id}
          route={r}
          isSelected={selectedId === r.id}
          onSelect={() => onSelect(r)}
        />
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    gap: 10,
    padding: '10px 16px',
    background: '#fff',
    borderTop: '1px solid #e5e7eb',
    overflowX: 'auto',
    alignItems: 'center',
    minHeight: 72,
  },
  msg: { fontSize: 13, color: '#6b7280' },
}
