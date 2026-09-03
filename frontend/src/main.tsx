import React, { Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import App from './App'
import './styles.css'

// 관리자 화면은 별도 청크로 나눠 일반 사용자 번들에 섞이지 않게 한다
const AdminApp = React.lazy(() => import('./admin/AdminApp'))

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<Suspense fallback={<div className="adm-boot">불러오는 중…</div>}><AdminApp /></Suspense>} />
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
