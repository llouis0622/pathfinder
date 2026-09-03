/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_VWORLD_KEY?: string
  readonly VITE_BASEMAP_STYLE_URL?: string
  readonly VITE_BACKEND_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
