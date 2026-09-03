import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AdminApp from '../admin/AdminApp'
import { adminLogin, exportUrl, fetchRequests } from '../admin/api'
import { BarChart, DivergingBars, LineChart, RankBars, ShareBar, fmtMs, fmtPct } from '../admin/charts'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const OVERVIEW = {
  generated_at: '2026-09-03T00:00:00Z',
  kpis: { requests_total: 12, requests_today: 3, requests_7d: 9, users_total: 2, users_new_7d: 1, active_users_7d: 2, choices_7d: 4, choose_rate_7d: 0.5,
    personalized_share_7d: 0.25, no_route_rate_7d: 0, error_rate_7d: 0, avg_elapsed_ms_7d: 210, learned_users: 1, access_errors_24h: 0 },
  series: Array.from({ length: 30 }, (_, i) => ({ date: `2026-08-${String(i + 1).padStart(2, '0')}`, requests: i, choices: 0, users: 0 })),
  profile_share: [{ profile: 'elderly', label: '고령자', count: 8 }, { profile: 'wheelchair', label: '휠체어', count: 4 }],
  recent_requests: [{ id: 'r1', created_at: '2026-09-03T01:00:00Z', user: null, user_id: null, profile: 'elderly', profile_label: '고령자',
    origin: { lat: 1, lng: 2, name: '서면역' }, destination: { lat: 3, lng: 4, name: '하단역' }, status: 'ok', error: null, elapsed_ms: 120,
    personalized: false, explored: false, prefer_shade: false, weather_flags: [], departure_at: null, n_results: 3, chosen_rank: 2 }],
  recent_auth: [],
}

describe('admin app', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows a setup notice when ADMIN_PASSWORD is not configured', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ configured: false, admin: false }))
    render(<MemoryRouter initialEntries={['/admin']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('관리자 기능이 꺼져 있어요')).toBeInTheDocument()
  })

  it('logs in with the password and renders the dashboard', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url === '/api/admin/me') return json({ configured: true, admin: false })
      if (url === '/api/admin/login') {
        const body = JSON.parse(String(init?.body))
        return body.password === 'pw' ? json({ admin: true }) : json({ detail: '비밀번호가 올바르지 않습니다' }, 401)
      }
      if (url === '/api/admin/overview') return json(OVERVIEW)
      return json({ detail: `unexpected ${url}` }, 404)
    })
    render(<MemoryRouter initialEntries={['/admin']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>)
    const input = await screen.findByLabelText('관리자 비밀번호')
    fireEvent.change(input, { target: { value: 'nope' } })
    fireEvent.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호가 올바르지 않습니다')
    fireEvent.change(input, { target: { value: 'pw' } })
    fireEvent.click(screen.getByRole('button', { name: '로그인' }))
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('대시보드'))
    expect(await screen.findByText('오늘 검색')).toBeInTheDocument()
    expect(screen.getByText('서면역 → 하단역')).toBeInTheDocument()
    expect(screen.getByText('2순위')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => String(u) === '/api/admin/overview')).toBe(true)
    // 관리자 메뉴가 모두 있다
    for (const label of ['경로 요청', '접근·인증', '엔진 성능', '경로 선택', '장소 검색', '사용자', '취향 분포', '이용 추이', '경로 품질', '공간 분석']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
  })
})

describe('admin api client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('builds query strings, sends credentials, and surfaces backend detail', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json({ items: [], total: 0, page: 1, size: 50, pages: 1 }))
      .mockResolvedValueOnce(json({ detail: '로그인 시도가 너무 많습니다' }, 429))
    await fetchRequests({ page: 2, profile: 'elderly', q: '', personalized: true })
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe('/api/admin/logs/requests?page=2&profile=elderly&personalized=true')
    expect(init?.credentials).toBe('include')
    await expect(adminLogin('x')).rejects.toMatchObject({ status: 429, message: '로그인 시도가 너무 많습니다' })
    expect(exportUrl('engine', 7)).toBe('/api/admin/export/engine.csv?days=7')
  })
})

describe('charts', () => {
  it('formats values and renders every chart with a table view', () => {
    expect(fmtPct(0.4567)).toBe('45.7%')
    expect(fmtMs(1530)).toBe('1.53s')
    expect(fmtMs(80)).toBe('80ms')
    render(
      <>
        <LineChart title="선" labels={['a', 'b', 'c']} series={[{ key: 'x', label: 'X', values: [1, 2, 3] }, { key: 'y', label: 'Y', values: [3, null, 1] }]} />
        <BarChart title="막대" labels={['월', '화']} values={[5, 0]} />
        <RankBars title="순위" items={[{ label: '서면역', value: 7 }, { label: '하단역', value: 3 }]} />
        <ShareBar title="비율" items={[{ label: '고령자', value: 3 }, { label: '휠체어', value: 1 }]} />
        <DivergingBars title="가중치" items={[{ key: 'walk', label: 'walk', value: -0.8, negativeLabel: '도보 적은 길 선호', positiveLabel: '도보 많아도 괜찮음' }]} />
      </>,
    )
    expect(screen.getAllByText('표로 보기')).toHaveLength(2)
    expect(screen.getByRole('img', { name: '선' })).toBeInTheDocument()
    expect(screen.getByText('서면역')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('-0.80')).toBeInTheDocument()
  })
})
