import { useEffect, useState, type RefObject } from 'react'

// Kakao Maps JS SDK 최소 타입
export interface KakaoLatLng {
  getLat(): number
  getLng(): number
}
export interface KakaoLatLngBounds {
  extend(latlng: KakaoLatLng): void
}
export interface KakaoMap {
  setCenter(latlng: KakaoLatLng): void
  setBounds(bounds: KakaoLatLngBounds, paddingTop?: number, paddingRight?: number, paddingBottom?: number, paddingLeft?: number): void
  relayout(): void
}
export interface KakaoOverlay {
  setMap(map: KakaoMap | null): void
}
export interface KakaoMaps {
  load(cb: () => void): void
  Map: new (container: HTMLElement, options: { center: KakaoLatLng; level: number }) => KakaoMap
  LatLng: new (lat: number, lng: number) => KakaoLatLng
  LatLngBounds: new () => KakaoLatLngBounds
  Marker: new (options: { position: KakaoLatLng; map?: KakaoMap; title?: string; zIndex?: number }) => KakaoOverlay
  Polyline: new (options: {
    path: KakaoLatLng[]
    strokeWeight?: number
    strokeColor?: string
    strokeOpacity?: number
    strokeStyle?: string
    zIndex?: number
    map?: KakaoMap
  }) => KakaoOverlay
  CustomOverlay: new (options: { position: KakaoLatLng; content: string; yAnchor?: number; zIndex?: number; map?: KakaoMap }) => KakaoOverlay
}

declare global {
  interface Window {
    kakao?: { maps: KakaoMaps }
  }
}

export type KakaoStatus = 'no-key' | 'loading' | 'ready' | 'error'

const BUSAN_CENTER = { lat: 35.1796, lng: 129.0756 }

export function useKakaoMap(containerRef: RefObject<HTMLDivElement | null>) {
  const [map, setMap] = useState<KakaoMap | null>(null)
  const [status, setStatus] = useState<KakaoStatus>('loading')

  useEffect(() => {
    const key = import.meta.env.VITE_KAKAO_MAP_KEY
    if (!key || key === 'YOUR_KAKAO_MAP_APP_KEY_HERE') {
      setStatus('no-key')
      return
    }
    let cancelled = false
    const init = () => {
      if (cancelled || !containerRef.current || !window.kakao) return
      const { maps } = window.kakao
      const instance = new maps.Map(containerRef.current, { center: new maps.LatLng(BUSAN_CENTER.lat, BUSAN_CENTER.lng), level: 6 })
      setMap(instance)
      setStatus('ready')
    }
    if (window.kakao?.maps) {
      window.kakao.maps.load(init)
      return
    }
    const existing = document.querySelector<HTMLScriptElement>('script[data-kakao-sdk]')
    const script = existing ?? document.createElement('script')
    if (!existing) {
      script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false`
      script.async = true
      script.dataset.kakaoSdk = '1'
      document.head.appendChild(script)
    }
    const onLoad = () => window.kakao?.maps.load(init)
    const onError = () => setStatus('error')
    script.addEventListener('load', onLoad)
    script.addEventListener('error', onError)
    return () => {
      cancelled = true
      script.removeEventListener('load', onLoad)
      script.removeEventListener('error', onError)
    }
  }, [containerRef])

  return { map, status }
}
