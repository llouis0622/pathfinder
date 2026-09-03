import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { exportUrl, fetchUserDetail, fetchUsers, resetUserPolicy } from '../api'
import { DivergingBars, LineChart, SERIES, ShareBar, StatTile, fmtMs, fmtNum, fmtPct } from '../charts'
import { Card, Filters, HttpStatus, Input, KIND_LABEL, Loading, PROVIDER_LABEL, Pager, Rank, Select, Status, Table, UserChip, fmtDate, fmtDateTime, profileLabel, useFetch } from '../ui'
import { FEATURE_LABELS } from './Preferences'

export function UsersPage() {
  const [q, setQ] = useState('')
  const [provider, setProvider] = useState('')
  const [sort, setSort] = useState('last_login')
  const [page, setPage] = useState(1)
  const nav = useNavigate()
  const { data, loading, error } = useFetch(() => fetchUsers({ page, size: 50, q, provider, sort }), [page, q, provider, sort])
  return (
    <Card title="사용자" actions={<a className="adm-btn" href={exportUrl('users')}>CSV</a>}>
      <Filters onReset={() => { setQ(''); setProvider(''); setSort('last_login'); setPage(1) }}>
        <Input label="닉네임" value={q} onChange={(v) => { setQ(v); setPage(1) }} placeholder="검색" />
        <Select label="로그인" value={provider} onChange={(v) => { setProvider(v); setPage(1) }} options={[{ value: '', label: '전체' }, ...(data?.providers ?? []).map((p) => ({ value: p.provider, label: `${PROVIDER_LABEL[p.provider] ?? p.provider} (${p.count})` }))]} />
        <Select label="정렬" value={sort} onChange={(v) => { setSort(v); setPage(1) }} options={[{ value: 'last_login', label: '최근 로그인' }, { value: 'created', label: '가입일' }, { value: 'requests', label: '검색 많은 순' }, { value: 'choices', label: '선택 많은 순' }, { value: 'updates', label: '학습 많은 순' }]} />
      </Filters>
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <Table head={['사용자', '가입', '최근 로그인', '검색', '선택', '학습', '취향 요약']}>
              {data.items.map((u) => (
                <tr key={u.id} className="is-click" onClick={() => nav(`/admin/users/${u.id}`)}>
                  <td><UserChip user={u} /></td><td>{fmtDate(u.created_at)}</td><td>{fmtDateTime(u.last_login_at)}</td>
                  <td>{fmtNum(u.requests)}</td><td>{fmtNum(u.choices)}</td><td>{fmtNum(u.updates)}</td>
                  <td className="wrap">{u.summary.length ? u.summary.join(' · ') : <span className="adm-muted">아직 없음</span>}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={7} className="adm-muted">사용자가 없어요</td></tr>}
            </Table>
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Loading>
    </Card>
  )
}

export function UserDetailPage() {
  const { id = '' } = useParams()
  const { data, loading, error, reload } = useFetch(() => fetchUserDetail(id), [id])
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const reset = async () => {
    if (!window.confirm('이 사용자의 학습된 취향을 초기화할까요? 되돌릴 수 없어요.')) return
    setBusy(true)
    try { await resetUserPolicy(id); reload() } finally { setBusy(false) }
  }
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          <div className="adm__toolbar">
            <Link className="adm-btn adm-btn--ghost" to="/admin/users">← 사용자 목록</Link>
            <div className="adm__top-actions">
              <Link className="adm-btn" to={`/admin/logs/requests?user_id=${data.user.id}`}>요청 로그</Link>
              <button type="button" className="adm-btn adm-btn--danger" disabled={busy || data.policy.updates === 0} onClick={reset}>취향 초기화</button>
            </div>
          </div>
          <div className="adm-grid adm-grid--tiles">
            <StatTile label="사용자" value={<UserChip user={data.user} />} sub={`가입 ${fmtDate(data.user.created_at)} · 최근 ${fmtDateTime(data.user.last_login_at)}`} />
            <StatTile label="검색" value={fmtNum(data.stats.requests)} sub={`개인화 적용 ${fmtNum(data.stats.personalized_requests)}`} />
            <StatTile label="경로 선택" value={fmtNum(data.stats.choices)} sub={`1순위 선택률 ${fmtPct(data.stats.rank1_choice_rate)}`} />
            <StatTile label="학습 횟수" value={fmtNum(data.policy.updates)} sub={data.policy.updated_at ? `갱신 ${fmtDateTime(data.policy.updated_at)}` : '아직 학습 전'} />
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="학습된 취향">
              {data.policy.updates > 0 ? (
                <>
                  <div className="adm-summary" style={{ marginBottom: 14 }}>{data.policy.summary.map((s) => <i key={s}>{s}</i>)}</div>
                  <DivergingBars items={Object.keys(FEATURE_LABELS).map((f) => ({ key: f, label: f, value: data.policy.weights[f] ?? 0, negativeLabel: FEATURE_LABELS[f][1], positiveLabel: FEATURE_LABELS[f][0] }))} max={3} />
                </>
              ) : <div className="adm-empty">경로를 고를수록 취향이 학습돼요</div>}
            </Card>
            <Card title="가중치 변화 이력">
              {data.policy_history.length > 0 ? (
                <LineChart height={240} labels={data.policy_history.map((_, i) => `${i + 1}회`)} format={(v) => v.toFixed(2)} series={topFeatures(data.policy_history.map((h) => h.weights_after)).map((f, i) => ({
                  key: f, label: FEATURE_LABELS[f]?.[0] ?? f, color: SERIES[i], values: data.policy_history.map((h) => h.weights_after[f] ?? 0),
                }))} />
              ) : <div className="adm-empty">아직 갱신 이력이 없어요</div>}
              {data.stats.profiles.length > 0 && <div style={{ marginTop: 14 }}><ShareBar title="사용 프로필" items={data.stats.profiles.map((p) => ({ label: p.label, value: p.count }))} /></div>}
            </Card>
          </div>
          <Card title="경로 선택 이력">
            <Table head={['시각', '프로필', '경로', '고른 순위', '제시 방식', '학습']}>
              {data.choices.map((c) => (
                <tr key={c.id} className="is-click" onClick={() => nav(`/admin/logs/requests/${c.request_id}`)}>
                  <td>{fmtDateTime(c.created_at)}</td><td>{profileLabel(c.profile)}</td><td className="wrap">{c.origin_name || '?'} → {c.dest_name || '?'}</td>
                  <td><Rank rank={c.shown_rank} /></td><td>{c.personalized ? (c.explored ? '개인화 · 탐험' : '개인화') : '엔진 순위'}</td><td>{c.learned ? '반영' : '–'}</td>
                </tr>
              ))}
              {data.choices.length === 0 && <tr><td colSpan={6} className="adm-muted">아직 없음</td></tr>}
            </Table>
          </Card>
          <div className="adm-grid adm-grid--2">
            <Card title="최근 검색">
              <Table head={['시각', '프로필', '경로', '상태', '선택']}>
                {data.recent_requests.map((r) => (
                  <tr key={r.id} className="is-click" onClick={() => nav(`/admin/logs/requests/${r.id}`)}>
                    <td>{fmtDateTime(r.created_at)}</td><td>{profileLabel(r.profile)}</td><td className="wrap">{r.origin.name || '?'} → {r.destination.name || '?'}</td>
                    <td><Status value={r.status} /></td><td><Rank rank={r.chosen_rank} /></td>
                  </tr>
                ))}
                {data.recent_requests.length === 0 && <tr><td colSpan={5} className="adm-muted">아직 없음</td></tr>}
              </Table>
            </Card>
            <Card title="최근 접근">
              <Table head={['시각', '종류', '경로', '상태', '응답']}>
                {data.recent_access.map((a) => (
                  <tr key={a.id}><td>{fmtDateTime(a.created_at)}</td><td>{KIND_LABEL[a.kind] ?? a.kind}</td><td className="adm-mono">{a.detail ?? `${a.method} ${a.path}`}</td><td><HttpStatus code={a.status} /></td><td>{fmtMs(a.duration_ms)}</td></tr>
                ))}
                {data.recent_access.length === 0 && <tr><td colSpan={5} className="adm-muted">아직 없음</td></tr>}
              </Table>
            </Card>
          </div>
        </>
      )}
    </Loading>
  )
}

/** 이력에서 절댓값이 가장 커진 특성 3개 (선 차트 계열 수 제한). */
function topFeatures(history: Record<string, number>[]): string[] {
  const last = history[history.length - 1] ?? {}
  return Object.keys(FEATURE_LABELS).sort((a, b) => Math.abs(last[b] ?? 0) - Math.abs(last[a] ?? 0)).slice(0, 3)
}
