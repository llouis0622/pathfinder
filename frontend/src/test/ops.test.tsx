import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AlertsPage, DataQualityPage, ReportsPage } from '../admin/pages/Ops'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const QUALITY = {
  graph: { source: 'grid_city', nodes: { total: 418, by_kind: { walk: 400, stop: 18 } }, edges: { total: 1540, by_kind: { walk: 1400, ride: 140 } },
    walk: { edges: 1400, length_km: 70.2, grade_coverage: 0.42, width_coverage: 0.1, surface_coverage: 0.9, stairs: 12, stairs_without_ramp: 3, steep_over_10pct: 7,
      kerbs: { lowered: 30 }, crossings: { traffic_signals: 12 }, tactile: { yes: 5, no: 2, unknown: 100 }, lit: { yes: 0, no: 0, unknown: 107 } },
    vertical: { edges: 15, elevator: { yes: 10, no: 2, unknown: 3 }, escalator: { yes: 0, no: 0, unknown: 15 } },
    transit: { stops: 18, platforms: 4, entrances: 6, routes: 3, low_floor_known: 20 },
    buildings: { total: 31, height_known: 30, height_coverage: 0.97 }, connectivity: { components: 1, largest_share: 1, isolated_walk_nodes: 0 } },
  reports: { open: 2, accepted: 1 }, active_overrides: 1, search_cache: { size: 3, maxsize: 500, hits: 6, misses: 4 },
}
const REPORT = { id: 'rep-1', created_at: '2026-09-03T01:00:00Z', user_id: null, user: null, request_id: null, lat: 35.15, lng: 129.06, kind: 'elevator_broken',
  kind_label: '엘리베이터 고장', note: '점검 중', place_name: 'A역', status: 'open', edge_id: null, edge_kind: '', admin_note: null, resolved_at: null }
const SETTINGS = { enabled: true, webhook_url: '', webhook_url_masked: '', webhook_configured: false, format: 'slack', interval_min: 5, window_min: 30, cooldown_min: 60,
  rules: { engine_down: { enabled: true }, error_rate: { enabled: true, threshold: 10, min_samples: 10 } }, rule_labels: { engine_down: '엔진 응답 없음', error_rate: '검색 오류율' } }

describe('ops pages', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders data quality tiles with warnings for low coverage', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(QUALITY))
    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)
    expect(await screen.findByText('경사 정보 커버리지')).toBeInTheDocument()
    expect(screen.getByText('42%').closest('.tile')).toHaveClass('tile--warn')
    expect(screen.getByText('97%').closest('.tile')).toHaveClass('tile--good')
    expect(screen.getByText(/적중률 60%/)).toBeInTheDocument()
  })

  it('accepts a report through the inline form', async () => {
    const calls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      if (url.startsWith('/api/admin/reports?')) return json({ items: [REPORT], total: 1, page: 1, size: 30, pages: 1, counts: { open: 1 }, kinds: { elevator_broken: '엘리베이터 고장' } })
      if (url.startsWith('/api/admin/overrides?')) return json({ items: [], total: 0, page: 1, size: 50, pages: 1 })
      if (url === '/api/admin/reports/rep-1/accept') return json({ report: { ...REPORT, status: 'accepted' }, override: { id: 'o1', edge_id: 1234, kind: 'elevator_broken', kind_label: '엘리베이터 고장', active: true, created_at: '', expires_at: null, note: '', report_id: 'rep-1', deactivated_at: null } })
      return json({ detail: `unexpected ${url}` }, 404)
    })
    render(<MemoryRouter><ReportsPage /></MemoryRouter>)
    expect(await screen.findByText('A역')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '반영…' }))
    fireEvent.click(screen.getByRole('button', { name: '반영' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('엣지 1234'))
    expect(calls.some((c) => c === 'POST /api/admin/reports/rep-1/accept')).toBe(true)
  })

  it('saves alert settings and shows evaluation findings', async () => {
    const bodies: unknown[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url === '/api/admin/alerts/settings' && init?.method === 'PUT') { bodies.push(JSON.parse(String(init.body))); return json({ ...SETTINGS, webhook_configured: true, webhook_url_masked: 'https://hooks.slack.com/servi…' }) }
      if (url === '/api/admin/alerts/settings') return json(SETTINGS)
      if (url.startsWith('/api/admin/alerts/events')) return json({ items: [], total: 0, page: 1, size: 30, pages: 1, rule_labels: {} })
      if (url === '/api/admin/limits') return json({ limits: { route_per_minute: 30, engine_concurrency: 4, engine_queue_timeout_s: 8 }, stats: { route_rejected: 0, engine_inflight: 0, engine_rejected: 0 }, defaults: { route_per_minute: 30, engine_concurrency: 4, engine_queue_timeout_s: 8 } })
      if (url === '/api/admin/alerts/evaluate') return json({ findings: [{ rule: 'error_rate', value: 50, threshold: 10, message: '검색 오류율 50%' }], sent: [], enabled: true, webhook_configured: false })
      return json({ detail: `unexpected ${url}` }, 404)
    })
    render(<MemoryRouter><AlertsPage /></MemoryRouter>)
    const urlInput = await screen.findByLabelText('웹훅 URL')
    fireEvent.change(urlInput, { target: { value: 'https://hooks.slack.com/services/x' } })
    fireEvent.change(screen.getByLabelText('검색 오류율 임계'), { target: { value: '25' } })
    fireEvent.click(screen.getByRole('button', { name: '저장' }))
    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toMatchObject({ webhook_url: 'https://hooks.slack.com/services/x', rules: { error_rate: { threshold: 25 } } })
    fireEvent.click(screen.getByRole('button', { name: '지금 평가' }))
    expect(await screen.findByText('검색 오류율 50%')).toBeInTheDocument()
  })
})
