/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_VWORLD_KEY?: string
  readonly VITE_BASEMAP_STYLE_URL?: string
  readonly VITE_BACKEND_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** vite.config.ts 의 define 으로 주입되는 빌드 식별자 (서비스 워커 캐시 이름) */
declare const __BUILD_ID__: string
