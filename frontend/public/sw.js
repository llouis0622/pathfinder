/* Pathfinder 서비스 워커.
 * - 화면 이동(index.html)·매니페스트: 네트워크 우선, 실패하면 캐시 → 새 배포가 바로 보이고 오프라인에서도 열린다
 * - /assets/ (파일명에 해시): 캐시 우선
 * - API: 네트워크 우선(경로 결과·프로필은 최근 응답을 보관), 타일: 캐시 우선
 */
const VERSION = 'pf-' + (new URL(self.location.href).searchParams.get('v') || 'dev')   // 빌드마다 다른 캐시
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png']
const OFFLINE_JSON = () => new Response(JSON.stringify({ detail: '오프라인 상태예요' }), { status: 503, headers: { 'Content-Type': 'application/json' } })

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL).catch(() => undefined)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()))
})

async function networkFirst(req, cacheKey) {
  const c = await caches.open(VERSION)
  try {
    const res = await fetch(req)
    if (res.status === 200) c.put(cacheKey || req, res.clone())
    return res
  } catch {
    const hit = await c.match(cacheKey || req)
    if (hit) return hit
    throw new Error('offline')
  }
}

async function cacheFirst(req) {
  const c = await caches.open(VERSION)
  const hit = await c.match(req)
  if (hit) return hit
  const res = await fetch(req)
  if (res.status === 200) c.put(req, res.clone())
  return res
}

/** 타일: 캐시가 있으면 바로 주고 뒤에서 갱신한다(빈 204 는 저장하지 않는다). 그래프를 새로 적재해도 곧 따라온다 */
async function staleWhileRevalidate(req) {
  const c = await caches.open(VERSION)
  const hit = await c.match(req)
  const refresh = fetch(req).then((res) => { if (res.status === 200) c.put(req, res.clone()); return res }).catch(() => undefined)
  if (hit) { refresh.catch(() => undefined); return hit }
  const res = await refresh
  if (!res) throw new Error('offline')
  return res
}

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return

  if (url.pathname.startsWith('/api/tiles/')) {
    event.respondWith(staleWhileRevalidate(req).catch(() => new Response(null, { status: 204 })))
    return
  }
  if (url.pathname.startsWith('/api/')) {
    const keep = url.pathname.startsWith('/api/route/') || url.pathname === '/api/profiles'
    event.respondWith(keep ? networkFirst(req).catch(OFFLINE_JSON) : fetch(req).catch(OFFLINE_JSON))
    return
  }
  if (req.mode === 'navigate') {
    // 어떤 경로로 들어와도 SPA 셸(index.html) 하나를 네트워크 우선으로
    event.respondWith(networkFirst(req, '/index.html').catch(() => caches.match('/index.html')))
    return
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(req))
    return
  }
  if (SHELL.includes(url.pathname)) {
    event.respondWith(networkFirst(req).catch(() => caches.match(req)))
  }
})
