/* Pathfinder 서비스 워커: 앱 셸은 캐시 우선, API 는 네트워크 우선(실패 시 최근 응답), 타일은 캐시 우선. */
const VERSION = 'pf-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL).catch(() => undefined)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()))
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/tiles/')) {
    event.respondWith(caches.open(VERSION).then(async (c) => {
      const hit = await c.match(req)
      if (hit) return hit
      const res = await fetch(req)
      if (res.ok) c.put(req, res.clone())
      return res
    }))
    return
  }
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(req).then((res) => {
      if (res.ok && (url.pathname.startsWith('/api/route/') || url.pathname === '/api/profiles')) caches.open(VERSION).then((c) => c.put(req, res.clone()))
      return res
    }).catch(() => caches.match(req).then((hit) => hit || new Response(JSON.stringify({ detail: '오프라인 상태예요' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))))
    return
  }
  event.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    if (res.ok && (url.pathname.startsWith('/assets/') || SHELL.includes(url.pathname))) caches.open(VERSION).then((c) => c.put(req, res.clone()))
    return res
  }).catch(() => (req.mode === 'navigate' ? caches.match('/index.html') : undefined))))
})
