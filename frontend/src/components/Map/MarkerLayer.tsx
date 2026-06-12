import { useEffect, useRef } from 'react'
import type { Place } from '../../types'
import type { KakaoMapInstance } from '../../hooks/useKakaoMap'

type Props = {
  map: KakaoMapInstance
  origin: Place | null
  destination: Place | null
}

// 출발지·도착지 마커 레이어
export default function MarkerLayer({ map, origin, destination }: Props) {
  const originMarkerRef = useRef<unknown>(null)
  const destMarkerRef = useRef<unknown>(null)

  useEffect(() => {
    const { kakao } = window
    if (!kakao?.maps) return

    // 이전 마커 제거
    if (originMarkerRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (originMarkerRef.current as any).setMap(null)
    }

    if (origin) {
      const marker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(origin.lat, origin.lng),
        map,
      })
      originMarkerRef.current = marker
      map.setCenter(new kakao.maps.LatLng(origin.lat, origin.lng))
    }
  }, [map, origin])

  useEffect(() => {
    const { kakao } = window
    if (!kakao?.maps) return

    if (destMarkerRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (destMarkerRef.current as any).setMap(null)
    }

    if (destination) {
      const marker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(destination.lat, destination.lng),
        map,
      })
      destMarkerRef.current = marker
    }
  }, [map, destination])

  return null
}
