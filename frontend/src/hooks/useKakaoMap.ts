import { useEffect, useRef, useState } from 'react'

declare global {
  interface Window {
    kakao: KakaoNamespace
  }
}

// 카카오맵 SDK 타입 (최소 정의)
interface KakaoNamespace {
  maps: {
    load: (callback: () => void) => void
    Map: new (container: HTMLElement, options: object) => KakaoMap
    Marker: new (options: object) => KakaoMarker
    LatLng: new (lat: number, lng: number) => KakaoLatLng
    Polyline: new (options: object) => KakaoPolyline
  }
}
interface KakaoMap {
  setCenter: (latlng: KakaoLatLng) => void
  getCenter: () => KakaoLatLng
}
interface KakaoMarker {
  setMap: (map: KakaoMap | null) => void
}
interface KakaoLatLng {
  getLat: () => number
  getLng: () => number
}
interface KakaoPolyline {
  setMap: (map: KakaoMap | null) => void
}

export type KakaoMapInstance = KakaoMap

// 카카오맵 초기화 훅
export function useKakaoMap(containerRef: React.RefObject<HTMLDivElement | null>) {
  const [map, setMap] = useState<KakaoMap | null>(null)
  const [isReady, setIsReady] = useState(false)
  const [hasKey, setHasKey] = useState(true)
  const scriptRef = useRef<HTMLScriptElement | null>(null)

  useEffect(() => {
    const apiKey = import.meta.env.VITE_KAKAO_MAP_KEY

    if (!apiKey || apiKey === 'YOUR_KAKAO_MAP_APP_KEY_HERE') {
      setHasKey(false)
      return
    }

    // 이미 로드된 경우
    if (window.kakao?.maps) {
      initMap()
      return
    }

    const script = document.createElement('script')
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${apiKey}&autoload=false`
    script.async = true
    script.onload = () => {
      window.kakao.maps.load(initMap)
    }
    document.head.appendChild(script)
    scriptRef.current = script

    function initMap() {
      if (!containerRef.current) return
      const instance = new window.kakao.maps.Map(containerRef.current, {
        center: new window.kakao.maps.LatLng(35.1796, 129.0756), // 부산역 기본 중심
        level: 7,
      })
      setMap(instance)
      setIsReady(true)
    }

    return () => {
      if (scriptRef.current) {
        document.head.removeChild(scriptRef.current)
      }
    }
  }, [containerRef])

  return { map, isReady, hasKey }
}
