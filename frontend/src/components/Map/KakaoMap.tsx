import { useRef } from 'react'
import { useKakaoMap } from '../../hooks/useKakaoMap'
import RouteLayer from './RouteLayer'
import MarkerLayer from './MarkerLayer'
import type { Coordinate, Place } from '../../types'

type Props = {
  origin: Place | null
  destination: Place | null
  routePath: Coordinate[]
}

// 카카오맵 컨테이너 컴포넌트
export default function KakaoMap({ origin, destination, routePath }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { map, isReady, hasKey } = useKakaoMap(containerRef)

  if (!hasKey) {
    return (
      <div style={styles.placeholder}>
        <p>카카오맵 API 키가 설정되지 않았습니다.</p>
        <p style={styles.sub}>
          <code>frontend/.env</code>에 <code>VITE_KAKAO_MAP_KEY</code>를 입력하세요.
        </p>
      </div>
    )
  }

  return (
    <div style={styles.wrapper}>
      <div ref={containerRef} style={styles.map} />
      {isReady && map && (
        <>
          <MarkerLayer map={map} origin={origin} destination={destination} />
          <RouteLayer map={map} path={routePath} />
        </>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { flex: 1, position: 'relative', minHeight: 0 },
  map: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  placeholder: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#f0f4f8',
    color: '#555',
    gap: 8,
  },
  sub: { fontSize: 13, color: '#888' },
}
