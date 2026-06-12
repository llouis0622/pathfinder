import { useEffect, useRef } from 'react'
import type { Coordinate } from '../../types'
import type { KakaoMapInstance } from '../../hooks/useKakaoMap'

type Props = {
  map: KakaoMapInstance
  path: Coordinate[]
}

// 경로 폴리라인 레이어
export default function RouteLayer({ map, path }: Props) {
  const polylineRef = useRef<unknown>(null)

  useEffect(() => {
    const { kakao } = window
    if (!kakao?.maps) return

    // 이전 폴리라인 제거
    if (polylineRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (polylineRef.current as any).setMap(null)
      polylineRef.current = null
    }

    if (path.length < 2) return

    const linePath = path.map((c) => new kakao.maps.LatLng(c.lat, c.lng))
    const polyline = new kakao.maps.Polyline({
      path: linePath,
      strokeWeight: 5,
      strokeColor: '#2563eb',
      strokeOpacity: 0.8,
      strokeStyle: 'solid',
      map,
    })
    polylineRef.current = polyline
  }, [map, path])

  return null
}
