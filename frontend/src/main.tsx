import React, { Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom'
import App from './App'
import './styles.css'

// 관리자 화면은 별도 청크로 나눠 일반 사용자 번들에 섞이지 않게 한다
const AdminApp = React.lazy(() => import('./admin/AdminApp'))

/** 공유 링크 /r/:requestId → 저장된 결과를 연다 */
function SharedRoute() {
  const { requestId } = useParams()
  return <App key={requestId} sharedRequestId={requestId} />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<Suspense fallback={<div className="adm-boot">불러오는 중…</div>}><AdminApp /></Suspense>} />
        <Route path="/r/:requestId" element={<SharedRoute />} />
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)

// PWA: 배포 빌드에서만 서비스 워커를 등록한다 (개발 서버에서는 HMR 과 충돌)
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js').catch(() => undefined) })
}
