/** 운영 화면: 데이터 품질, 시설 제보 검토·오버라이드, 알림(웹훅·임계). */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  acceptReport, createOverride, deactivateOverride, evaluateAlerts, fetchAlertEvents, fetchAlertSettings, fetchDataQuality, fetchOverrides,
  fetchLimits, fetchReports, rejectReport, saveAlertSettings, saveLimits, testAlert, type AlertFinding, type AlertRule, type AlertSettings, type GraphStats, type Limits, type ReportRow,
} from '../api'
import { RankBars, ShareBar, StatTile, fmtNum, fmtPct } from '../charts'
import { Card, Empty, Filters, Input, Loading, Pager, Select, Table, UserChip, fmtDateTime, useFetch } from '../ui'

const NODE_LABEL: Record<string, string> = { walk: '보행', stop: '정류장', route_stop: '노선별 정류장', platform: '승강장', entrance: '출입구' }
const EDGE_LABEL: Record<string, string> = { walk: '보행', link: '연결', vertical: '수직 이동', board: '승차', ride: '탑승', alight: '하차', transfer: '환승' }
const KERB_LABEL: Record<string, string> = { lowered: '낮춤턱', flush: '단차 없음', raised: '턱 있음', no: '턱 없음', yes: '턱 있음' }
const CROSSING_LABEL: Record<string, string> = { traffic_signals: '신호 있음', uncontrolled: '신호 없음', zebra: '횡단보도', marked: '표시됨', unmarked: '표시 없음' }
const REPORT_STATUS: Record<string, string> = { open: '검토 대기', accepted: '반영됨', rejected: '거절' }
const OVERRIDE_KINDS = [{ value: 'elevator_broken', label: '엘리베이터 고장' }, { value: 'stairs', label: '계단 있음' }, { value: 'kerb', label: '턱 있음' }, { value: 'blocked', label: '통행 불가' }, { value: 'ok', label: '문제 없음(정정)' }]

function Tri({ label, tri }: { label: string; tri?: { yes: number; no: number; unknown: number } }) {
  if (!tri) return null
  const total = tri.yes + tri.no + tri.unknown
  return (
    <div>
      {label}
      <b>{fmtNum(tri.yes)} 확인 <small className="adm-muted">/ 없음 {fmtNum(tri.no)} · 미확인 {fmtNum(tri.unknown)}{total ? ` (${fmtPct(tri.unknown / total, 0)} 미확인)` : ''}</small></b>
    </div>
  )
}

function coverageTone(v: number | null | undefined): 'warn' | 'good' | undefined {
  if (v === null || v === undefined) return undefined
  return v < 0.6 ? 'warn' : v >= 0.9 ? 'good' : undefined
}

export function DataQualityPage() {
  const { data, loading, error, reload } = useFetch(fetchDataQuality, [])
  const g: GraphStats = data?.graph ?? {}
  const reports = data?.reports ?? {}
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          {g.error && <div className="adm-error" role="alert">엔진 통계를 가져오지 못했어요: {g.error}</div>}
          <div className="adm-grid adm-grid--tiles">
            <StatTile label="보행 엣지" value={fmtNum(g.walk?.edges)} sub={g.walk?.length_km !== undefined ? `${fmtNum(g.walk.length_km, 1)} km · 노드 ${fmtNum(g.nodes?.total)}` : `노드 ${fmtNum(g.nodes?.total)}`} />
            <StatTile label="경사 정보 커버리지" value={fmtPct(g.walk?.grade_coverage, 0)} tone={coverageTone(g.walk?.grade_coverage)} sub="DEM 으로 경사를 계산한 보행 엣지 비율" />
            <StatTile label="건물 높이 커버리지" value={fmtPct(g.buildings?.height_coverage, 0)} tone={coverageTone(g.buildings?.height_coverage)} sub={`${fmtNum(g.buildings?.height_known)} / ${fmtNum(g.buildings?.total)} 동 (그늘 계산 근거)`} />
            <StatTile label="보행망 연결성" value={fmtPct(g.connectivity?.largest_share, 0)} tone={coverageTone(g.connectivity?.largest_share)} sub={`덩어리 ${fmtNum(g.connectivity?.components)}개 · 고립 노드 ${fmtNum(g.connectivity?.isolated_walk_nodes)}`} />
            <StatTile label="검토 대기 제보" value={fmtNum(reports.open ?? 0)} tone={(reports.open ?? 0) > 0 ? 'warn' : undefined} sub={`반영 ${fmtNum(reports.accepted ?? 0)} · 거절 ${fmtNum(reports.rejected ?? 0)}`} />
            <StatTile label="활성 오버라이드" value={fmtNum(data.active_overrides)} sub="검색에 적용 중인 제보 반영" />
            <StatTile label="검색 캐시" value={data.search_cache ? `${fmtNum(data.search_cache.size)} / ${fmtNum(data.search_cache.maxsize)}` : '꺼짐'}
              sub={data.search_cache ? `적중 ${fmtNum(data.search_cache.hits)} · 실패 ${fmtNum(data.search_cache.misses)}${data.search_cache.hits + data.search_cache.misses ? ` · 적중률 ${fmtPct(data.search_cache.hits / (data.search_cache.hits + data.search_cache.misses), 0)}` : ''}` : undefined} />
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="보행 엣지 속성" actions={<span className="adm-muted">{g.source ?? ''}</span>}>
              <div className="adm-kv">
                <div>폭 정보<b>{fmtPct(g.walk?.width_coverage, 0)}</b></div>
                <div>노면 정보<b>{fmtPct(g.walk?.surface_coverage, 0)}</b></div>
                <div>계단 구간<b>{fmtNum(g.walk?.stairs)} <small className="adm-muted">경사로 없음 {fmtNum(g.walk?.stairs_without_ramp)}</small></b></div>
                <div>10% 초과 급경사<b>{fmtNum(g.walk?.steep_over_10pct)}</b></div>
                <Tri label="점자블록" tri={g.walk?.tactile} />
                <Tri label="가로등" tri={g.walk?.lit} />
                <Tri label="엘리베이터(수직 이동)" tri={g.vertical?.elevator} />
                <Tri label="에스컬레이터" tri={g.vertical?.escalator} />
              </div>
            </Card>
            <Card title="대중교통·노드">
              <div className="adm-kv">
                <div>정류장<b>{fmtNum(g.transit?.stops)}</b></div>
                <div>승강장<b>{fmtNum(g.transit?.platforms)}</b></div>
                <div>출입구<b>{fmtNum(g.transit?.entrances)}</b></div>
                <div>노선<b>{fmtNum(g.transit?.routes)}</b></div>
                <div>저상 비율 알려진 승차 엣지<b>{fmtNum(g.transit?.low_floor_known)}</b></div>
                <div>엣지 전체<b>{fmtNum(g.edges?.total)}</b></div>
              </div>
              {g.edges?.by_kind && <div style={{ marginTop: 14 }}><ShareBar title="엣지 종류" items={Object.entries(g.edges.by_kind).map(([k, v]) => ({ label: EDGE_LABEL[k] ?? k, value: v }))} /></div>}
              {g.nodes?.by_kind && <div style={{ marginTop: 14 }}><ShareBar title="노드 종류" items={Object.entries(g.nodes.by_kind).map(([k, v]) => ({ label: NODE_LABEL[k] ?? k, value: v }))} /></div>}
            </Card>
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="턱(연석) 정보"><RankBars items={Object.entries(g.walk?.kerbs ?? {}).map(([k, v]) => ({ label: KERB_LABEL[k] ?? k, value: v }))} empty="턱 정보가 없어요" /></Card>
            <Card title="횡단 정보"><RankBars items={Object.entries(g.walk?.crossings ?? {}).map(([k, v]) => ({ label: CROSSING_LABEL[k] ?? k, value: v }))} empty="횡단 정보가 없어요" /></Card>
          </div>
          <div className="adm__top-actions">
            <button type="button" className="adm-btn" onClick={reload}>다시 계산</button>
            <Link className="adm-link" to="/admin/reports">제보 검토로</Link>
            <span className="adm-muted">커버리지가 낮은 항목은 docs/DATA_PIPELINE.md 의 해당 단계(DEM·VWorld 높이·OSM 태그)를 다시 돌리면 올라가요.</span>
          </div>
        </>
      )}
    </Loading>
  )
}

// ---------------------------------------------------------------- 제보 검토
function AcceptForm({ report, onDone, onCancel }: { report: ReportRow; onDone: (msg: string) => void; onCancel: () => void }) {
  const [kind, setKind] = useState(OVERRIDE_KINDS.some((k) => k.value === report.kind) ? report.kind : 'blocked')
  const [edgeId, setEdgeId] = useState('')
  const [days, setDays] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const submit = async () => {
    setBusy(true); setErr(null)
    try {
      const r = await acceptReport(report.id, { kind, edge_id: edgeId ? Number(edgeId) : undefined, expires_days: days ? Number(days) : undefined, note })
      onDone(`반영했어요 · 엣지 ${r.override.edge_id} (${r.override.kind_label})`)
    } catch (e) { setErr(e instanceof Error ? e.message : '반영하지 못했어요') } finally { setBusy(false) }
  }
  return (
    <div className="adm-inline" role="group" aria-label="제보 반영">
      <Select label="반영 종류" value={kind} onChange={setKind} options={OVERRIDE_KINDS} />
      <Input label="엣지 ID (비우면 자동)" value={edgeId} onChange={setEdgeId} placeholder="가장 가까운 보행 엣지" />
      <Input label="만료 (일, 선택)" value={days} onChange={setDays} type="number" placeholder="예: 7" />
      <Input label="메모" value={note} onChange={setNote} placeholder="검토 메모" />
      <button type="button" className="adm-btn adm-btn--primary" disabled={busy} onClick={submit}>{busy ? '반영 중…' : '반영'}</button>
      <button type="button" className="adm-btn adm-btn--ghost" onClick={onCancel}>취소</button>
      {err && <span className="adm-error" role="alert">{err}</span>}
    </div>
  )
}

export function ReportsPage() {
  const [status, setStatus] = useState('open')
  const [kind, setKind] = useState('')
  const [page, setPage] = useState(1)
  const [acting, setActing] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const { data, loading, error, reload } = useFetch(() => fetchReports({ status, kind, page, size: 30 }), [status, kind, page])
  const ov = useFetch(() => fetchOverrides({ active: true, page: 1, size: 50 }), [])
  const [newEdge, setNewEdge] = useState('')
  const [newKind, setNewKind] = useState('blocked')
  const [newDays, setNewDays] = useState('')
  const done = (m: string) => { setMsg(m); setActing(null); reload(); ov.reload() }
  const reject = async (r: ReportRow) => {
    const note = window.prompt('거절 사유 (선택)', '') ?? null
    if (note === null) return
    try { await rejectReport(r.id, note); done('거절했어요') } catch (e) { setMsg(e instanceof Error ? e.message : '거절하지 못했어요') }
  }
  const off = async (id: string) => {
    if (!window.confirm('이 오버라이드를 해제할까요? 검색 결과에서 바로 빠져요.')) return
    try { await deactivateOverride(id); done('해제했어요') } catch (e) { setMsg(e instanceof Error ? e.message : '해제하지 못했어요') }
  }
  const addOverride = async () => {
    if (!newEdge) return
    try { await createOverride({ edge_id: Number(newEdge), kind: newKind, expires_days: newDays ? Number(newDays) : undefined }); setNewEdge(''); done('오버라이드를 추가했어요') } catch (e) { setMsg(e instanceof Error ? e.message : '추가하지 못했어요') }
  }
  const counts = data?.counts ?? {}
  return (
    <>
      <div className="adm-grid adm-grid--tiles">
        <StatTile label="검토 대기" value={fmtNum(counts.open ?? 0)} tone={(counts.open ?? 0) > 0 ? 'warn' : undefined} />
        <StatTile label="반영됨" value={fmtNum(counts.accepted ?? 0)} />
        <StatTile label="거절" value={fmtNum(counts.rejected ?? 0)} />
        <StatTile label="활성 오버라이드" value={fmtNum(ov.data?.total ?? 0)} sub="검색에 적용 중" />
      </div>
      <Card title="시설 제보" actions={msg && <span className="adm-muted" role="status">{msg}</span>}>
        <Filters onReset={() => { setStatus('open'); setKind(''); setPage(1) }}>
          <Select label="상태" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[{ value: '', label: '전체' }, { value: 'open', label: '검토 대기' }, { value: 'accepted', label: '반영됨' }, { value: 'rejected', label: '거절' }]} />
          <Select label="종류" value={kind} onChange={(v) => { setKind(v); setPage(1) }} options={[{ value: '', label: '전체' }, ...Object.entries(data?.kinds ?? {}).map(([value, label]) => ({ value, label }))]} />
        </Filters>
        <Loading loading={loading} error={error}>
          {data && data.items.length === 0 && <Empty text="해당하는 제보가 없어요" />}
          {data && data.items.length > 0 && (
            <>
              <Table head={['시각', '종류', '장소·메모', '위치', '제보자', '상태', '처리']}>
                {data.items.map((r) => (
                  <>
                    <tr key={r.id}>
                      <td>{fmtDateTime(r.created_at)}</td><td><span className={`adm-status adm-status--${r.kind === 'ok' ? 'ok' : 'warn'}`}>{r.kind_label}</span></td>
                      <td className="wrap"><b>{r.place_name || '—'}</b>{r.note && <div className="adm-muted">{r.note}</div>}{r.admin_note && <div className="adm-muted">관리자: {r.admin_note}</div>}</td>
                      <td className="adm-mono">{r.lat.toFixed(5)}, {r.lng.toFixed(5)}{r.edge_id !== null && <div>엣지 {r.edge_id}</div>}</td>
                      <td><UserChip user={r.user} id={r.user_id} /></td>
                      <td><span className={`adm-status adm-status--${r.status === 'accepted' ? 'ok' : r.status === 'rejected' ? 'error' : 'warn'}`}>{REPORT_STATUS[r.status] ?? r.status}</span></td>
                      <td>
                        {r.status === 'open' && (
                          <div className="adm__top-actions">
                            <button type="button" className="adm-btn adm-btn--primary" onClick={() => setActing(acting === r.id ? null : r.id)}>반영…</button>
                            <button type="button" className="adm-btn" onClick={() => reject(r)}>거절</button>
                          </div>
                        )}
                        {r.request_id && <Link className="adm-link" to={`/admin/logs/requests/${r.request_id}`} style={{ marginLeft: 8 }}>요청</Link>}
                      </td>
                    </tr>
                    {acting === r.id && <tr key={`${r.id}-form`}><td colSpan={7}><AcceptForm report={r} onDone={done} onCancel={() => setActing(null)} /></td></tr>}
                  </>
                ))}
              </Table>
              <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
            </>
          )}
        </Loading>
      </Card>
      <Card title="활성 오버라이드" actions={<span className="adm-muted">검색 요청마다 엔진에 전달돼 해당 엣지를 막거나 되살려요</span>}>
        <div className="adm-inline" role="group" aria-label="오버라이드 직접 추가">
          <Input label="엣지 ID" value={newEdge} onChange={setNewEdge} type="number" placeholder="지도 시설 레이어에서 확인" />
          <Select label="종류" value={newKind} onChange={setNewKind} options={OVERRIDE_KINDS} />
          <Input label="만료 (일)" value={newDays} onChange={setNewDays} type="number" placeholder="비우면 무기한" />
          <button type="button" className="adm-btn" disabled={!newEdge} onClick={addOverride}>추가</button>
        </div>
        <Loading loading={ov.loading} error={ov.error}>
          {ov.data && ov.data.items.length === 0 && <Empty text="활성 오버라이드가 없어요" />}
          {ov.data && ov.data.items.length > 0 && (
            <Table head={['시각', '엣지', '종류', '만료', '메모', '제보', '']} className="adm-table--compact">
              {ov.data.items.map((o) => (
                <tr key={o.id}>
                  <td>{fmtDateTime(o.created_at)}</td><td className="adm-mono">{o.edge_id}</td><td>{o.kind_label}</td><td>{o.expires_at ? fmtDateTime(o.expires_at) : '무기한'}</td>
                  <td className="wrap">{o.note}</td><td className="adm-mono">{o.report_id ? o.report_id.slice(0, 8) : '직접'}</td>
                  <td><button type="button" className="adm-btn adm-btn--danger" onClick={() => off(o.id)}>해제</button></td>
                </tr>
              ))}
            </Table>
          )}
        </Loading>
      </Card>
    </>
  )
}

// ---------------------------------------------------------------- 요청 한도·동시성
export function LimitsCard() {
  const { data, loading, error, reload } = useFetch(fetchLimits, [])
  const [form, setForm] = useState<Partial<Limits>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const cur: Limits | null = data ? { ...data.limits, ...form } : null
  const save = async () => {
    if (!cur) return
    try { await saveLimits(cur); setForm({}); setMsg('저장했어요 (바로 적용)'); reload() } catch (e) { setMsg(e instanceof Error ? e.message : '저장하지 못했어요') }
  }
  return (
    <Card title="요청 한도·엔진 동시성" actions={data && <span className="adm-muted">거절 · 검색 {fmtNum(data.stats.route_rejected)} · 엔진 혼잡 {fmtNum(data.stats.engine_rejected)} · 진행 중 {fmtNum(data.stats.engine_inflight)}</span>}>
      <Loading loading={loading} error={error}>
        {cur && (
          <>
            <p className="adm-muted" style={{ marginBottom: 10 }}>무료 공개 서비스에서 한 IP 가 검색을 쏟아붓거나, 검색이 몰려 엔진이 과부하되는 것을 막아요. 한도를 넘으면 429, 엔진 자리가 안 나면 503 을 돌려주고 프론트가 안내 문구를 보여 줘요.</p>
            <div className="adm-inline">
              <Input label="IP 당 분당 검색 (0 = 제한 없음)" type="number" value={String(cur.route_per_minute)} onChange={(v) => setForm({ ...form, route_per_minute: Number(v) })} />
              <Input label="엔진 동시 탐색 수" type="number" value={String(cur.engine_concurrency)} onChange={(v) => setForm({ ...form, engine_concurrency: Number(v) })} />
              <Input label="대기 시간 (초)" type="number" value={String(cur.engine_queue_timeout_s)} onChange={(v) => setForm({ ...form, engine_queue_timeout_s: Number(v) })} />
              <button type="button" className="adm-btn adm-btn--primary" disabled={Object.keys(form).length === 0} onClick={save}>한도 저장</button>
              {msg && <span className="adm-muted" role="status">{msg}</span>}
            </div>
            <p className="adm-muted">환경변수 기본값: 분당 {data?.defaults.route_per_minute} · 동시 {data?.defaults.engine_concurrency} · 대기 {data?.defaults.engine_queue_timeout_s}초. 엔진 쪽에도 같은 보호(<code>MAX_CONCURRENT_SEARCHES</code>)가 있어요.</p>
          </>
        )}
      </Loading>
    </Card>
  )
}

// ---------------------------------------------------------------- 알림
const RULE_HELP: Record<string, { unit: string; help: string }> = {
  engine_down: { unit: '', help: '엔진 /health 가 200 이 아니면' },
  error_rate: { unit: '%', help: '창 안 검색 중 오류 비율이 넘으면 (표본 최소 N건)' },
  no_route_rate: { unit: '%', help: '창 안 검색 중 경로 없음 비율이 넘으면' },
  engine_p95_ms: { unit: 'ms', help: '창 안 엔진 응답 p95 가 넘으면' },
  access_5xx: { unit: '건', help: '창 안 서버 오류(5xx) 응답 수가 이 값 이상이면' },
  open_reports: { unit: '건', help: '검토 대기 제보가 이 값 이상이면' },
}

export function AlertsPage() {
  const { data, loading, error, reload } = useFetch(fetchAlertSettings, [])
  const events = useFetch(() => fetchAlertEvents({ page: 1, size: 30 }), [])
  const [form, setForm] = useState<Partial<AlertSettings> | null>(null)
  const [url, setUrl] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [findings, setFindings] = useState<AlertFinding[] | null>(null)
  const [busy, setBusy] = useState(false)
  const s: AlertSettings | null = data ? { ...data, ...(form ?? {}) } : null
  const setRule = (rule: string, patch: Partial<AlertRule>) => s && setForm({ ...(form ?? {}), rules: { ...s.rules, [rule]: { ...s.rules[rule], ...patch } } })
  const save = async () => {
    if (!s) return
    setBusy(true); setMsg(null)
    try {
      const patch: Parameters<typeof saveAlertSettings>[0] = { enabled: s.enabled, format: s.format, interval_min: s.interval_min, window_min: s.window_min, cooldown_min: s.cooldown_min, rules: s.rules }
      if (url) patch.webhook_url = url
      await saveAlertSettings(patch)
      setForm(null); setUrl(''); setMsg('저장했어요'); reload()
    } catch (e) { setMsg(e instanceof Error ? e.message : '저장하지 못했어요') } finally { setBusy(false) }
  }
  const clearUrl = async () => {
    if (!window.confirm('웹훅 URL 을 지우면 알림이 나가지 않아요. 지울까요?')) return
    try { await saveAlertSettings({ webhook_url: '' }); setMsg('웹훅을 지웠어요'); reload() } catch (e) { setMsg(e instanceof Error ? e.message : '실패') }
  }
  const test = async () => {
    setBusy(true)
    try { const ev = await testAlert(); setMsg(ev.sent ? `테스트 전송 성공 (HTTP ${ev.http_status})` : `테스트 전송 실패: ${ev.error || ev.http_status}`); events.reload() } catch (e) { setMsg(e instanceof Error ? e.message : '실패') } finally { setBusy(false) }
  }
  const evaluate = async () => {
    setBusy(true)
    try { const r = await evaluateAlerts(); setFindings(r.findings); setMsg(r.findings.length ? `${r.findings.length}개 규칙이 임계를 넘었어요${r.sent.length ? ` · ${r.sent.length}건 전송` : r.webhook_configured ? ' · 쿨다운으로 전송 없음' : ' · 웹훅 없음'}` : '모든 규칙 정상'); events.reload() } catch (e) { setMsg(e instanceof Error ? e.message : '실패') } finally { setBusy(false) }
  }
  return (
    <Loading loading={loading} error={error}>
      {s && (
        <>
          <div className="adm-grid adm-grid--2">
            <Card title="웹훅" actions={<span className={`adm-status adm-status--${s.webhook_configured && s.enabled ? 'ok' : 'warn'}`}>{s.webhook_configured ? (s.enabled ? '켜짐' : '꺼짐') : '웹훅 없음'}</span>}>
              <p className="adm-muted" style={{ marginBottom: 10 }}>Slack 수신 웹훅(Incoming Webhook) URL 을 넣으면 임계를 넘을 때 채널로 보내요. Discord·Teams·자체 서버는 형식을 JSON 으로 두고 받으면 돼요. 환경변수 <code>ALERT_WEBHOOK_URL</code> 로도 넣을 수 있고, 여기서 저장한 값이 우선해요.</p>
              <div className="adm-inline">
                <Input label={`웹훅 URL${s.webhook_configured ? ` (현재 ${s.webhook_url_masked})` : ''}`} value={url} onChange={setUrl} placeholder="https://hooks.slack.com/services/…" />
                <Select label="형식" value={s.format} onChange={(v) => setForm({ ...(form ?? {}), format: v as 'slack' | 'json' })} options={[{ value: 'slack', label: 'Slack (text)' }, { value: 'json', label: 'JSON' }]} />
                <label className="adm-field"><span>알림</span><label className="adm-check"><input type="checkbox" checked={s.enabled} onChange={(e) => setForm({ ...(form ?? {}), enabled: e.target.checked })} /> 켜기</label></label>
              </div>
              <div className="adm-inline">
                <Input label="평가 주기 (분)" type="number" value={String(s.interval_min)} onChange={(v) => setForm({ ...(form ?? {}), interval_min: Number(v) })} />
                <Input label="집계 창 (분)" type="number" value={String(s.window_min)} onChange={(v) => setForm({ ...(form ?? {}), window_min: Number(v) })} />
                <Input label="같은 규칙 재알림 간격 (분)" type="number" value={String(s.cooldown_min)} onChange={(v) => setForm({ ...(form ?? {}), cooldown_min: Number(v) })} />
              </div>
              <div className="adm__top-actions" style={{ marginTop: 12 }}>
                <button type="button" className="adm-btn adm-btn--primary" disabled={busy || (!form && !url)} onClick={save}>저장</button>
                <button type="button" className="adm-btn" disabled={busy || !s.webhook_configured} onClick={test}>테스트 전송</button>
                <button type="button" className="adm-btn" disabled={busy} onClick={evaluate}>지금 평가</button>
                {s.webhook_configured && <button type="button" className="adm-btn adm-btn--ghost" disabled={busy} onClick={clearUrl}>웹훅 지우기</button>}
                {msg && <span className="adm-muted" role="status">{msg}</span>}
              </div>
              {findings && (
                <div style={{ marginTop: 12 }}>
                  {findings.length === 0 ? <div className="adm-status adm-status--ok">모든 규칙 정상</div> : (
                    <ul className="adm-list">{findings.map((f) => <li key={f.rule}><span className="adm-status adm-status--warn">{s.rule_labels[f.rule] ?? f.rule}</span> {f.message}</li>)}</ul>
                  )}
                </div>
              )}
            </Card>
            <Card title="규칙·임계">
              <Table head={['규칙', '켜기', '임계', '최소 표본', '설명']} className="adm-table--compact">
                {Object.entries(s.rules).map(([rule, r]) => (
                  <tr key={rule}>
                    <td><b>{s.rule_labels[rule] ?? rule}</b></td>
                    <td><input type="checkbox" aria-label={`${s.rule_labels[rule] ?? rule} 켜기`} checked={r.enabled} onChange={(e) => setRule(rule, { enabled: e.target.checked })} /></td>
                    <td>{r.threshold !== undefined ? <span className="adm-inline adm-inline--tight"><input type="number" className="adm-num" aria-label={`${s.rule_labels[rule] ?? rule} 임계`} value={r.threshold} onChange={(e) => setRule(rule, { threshold: Number(e.target.value) })} /> {RULE_HELP[rule]?.unit}</span> : <span className="adm-muted">—</span>}</td>
                    <td>{r.min_samples !== undefined ? <input type="number" className="adm-num" aria-label={`${s.rule_labels[rule] ?? rule} 최소 표본`} value={r.min_samples} onChange={(e) => setRule(rule, { min_samples: Number(e.target.value) })} /> : <span className="adm-muted">—</span>}</td>
                    <td className="wrap adm-muted">{RULE_HELP[rule]?.help}</td>
                  </tr>
                ))}
              </Table>
            </Card>
          </div>
          <LimitsCard />
          <Card title="알림 이력" actions={<button type="button" className="adm-btn adm-btn--ghost" onClick={events.reload}>새로고침</button>}>
            <Loading loading={events.loading} error={events.error}>
              {events.data && events.data.items.length === 0 && <Empty text="아직 보낸 알림이 없어요" />}
              {events.data && events.data.items.length > 0 && (
                <Table head={['시각', '규칙', '수준', '내용', '값', '전송']} className="adm-table--compact">
                  {events.data.items.map((e) => (
                    <tr key={e.id}>
                      <td>{fmtDateTime(e.created_at)}</td><td>{e.rule_label}</td>
                      <td><span className={`adm-status adm-status--${e.level === 'ok' ? 'ok' : e.level === 'test' ? '' : 'warn'}`}>{e.level === 'ok' ? '복구' : e.level === 'test' ? '테스트' : '경고'}</span></td>
                      <td className="wrap">{e.message}</td><td className="adm-mono">{e.value ?? ''}{e.threshold !== null ? ` / ${e.threshold}` : ''}</td>
                      <td>{e.sent ? <span className="adm-status adm-status--ok">보냄 {e.http_status}</span> : <span className="adm-status adm-status--error" title={e.error}>실패 {e.http_status ?? ''} {e.error}</span>}</td>
                    </tr>
                  ))}
                </Table>
              )}
            </Loading>
          </Card>
        </>
      )}
    </Loading>
  )
}
