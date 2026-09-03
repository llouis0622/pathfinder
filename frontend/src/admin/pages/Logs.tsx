import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { exportUrl, fetchAccess, fetchChoices, fetchEngineLogs, fetchPlaces, fetchRequests } from '../api'
import { fmtMs, fmtNum, fmtPct } from '../charts'
import { Card, Chips, Filters, HttpStatus, Input, KIND_LABEL, Loading, Pager, Rank, Select, Status, Table, UserChip, fmtDateTime, flagLabel, profileLabel, useFetch } from '../ui'

const PROFILE_OPTIONS = [{ value: '', label: '전체' }, { value: 'wheelchair', label: '휠체어' }, { value: 'elderly', label: '고령자' },
  { value: 'walking_aid', label: '보행보조' }, { value: 'visually_impaired', label: '시각장애' }]

function usePage() {
  const [page, setPage] = useState(1)
  return { page, setPage, reset: () => setPage(1) }
}

function ExportLink({ kind }: { kind: 'requests' | 'choices' | 'users' | 'access' | 'engine' }) {
  return <a className="adm-btn" href={exportUrl(kind, 30)}>CSV (30일)</a>
}

export function RequestsLog() {
  const [sp] = useSearchParams()
  const [profile, setProfile] = useState('')
  const [status, setStatus] = useState('')
  const [personalized, setPersonalized] = useState('')
  const [q, setQ] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const userId = sp.get('user_id') ?? ''
  const { page, setPage, reset } = usePage()
  const nav = useNavigate()
  const { data, loading, error } = useFetch(() => fetchRequests({ page, size: 50, profile, status, q, from, to, user_id: userId,
    personalized: personalized === '' ? undefined : personalized === 'true' }), [page, profile, status, personalized, q, from, to, userId])
  return (
    <Card title={userId ? '사용자의 경로 요청' : '경로 요청 로그'} actions={<ExportLink kind="requests" />}>
      <Filters onReset={() => { setProfile(''); setStatus(''); setPersonalized(''); setQ(''); setFrom(''); setTo(''); reset() }}>
        <Select label="프로필" value={profile} onChange={(v) => { setProfile(v); reset() }} options={PROFILE_OPTIONS} />
        <Select label="상태" value={status} onChange={(v) => { setStatus(v); reset() }} options={[{ value: '', label: '전체' }, { value: 'ok', label: '성공' }, { value: 'no_route', label: '경로 없음' }, { value: 'error', label: '오류' }]} />
        <Select label="개인화" value={personalized} onChange={(v) => { setPersonalized(v); reset() }} options={[{ value: '', label: '전체' }, { value: 'true', label: '적용' }, { value: 'false', label: '미적용' }]} />
        <Input label="출발/도착 검색" value={q} onChange={(v) => { setQ(v); reset() }} placeholder="예: 서면" />
        <Input label="시작일" type="date" value={from} onChange={(v) => { setFrom(v); reset() }} />
        <Input label="종료일" type="date" value={to} onChange={(v) => { setTo(v); reset() }} />
      </Filters>
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <Table head={['시각', '사용자', '프로필', '출발 → 도착', '상태', '결과', '선택', '개인화', '날씨', '응답']}>
              {data.items.map((r) => (
                <tr key={r.id} className="is-click" onClick={() => nav(`/admin/logs/requests/${r.id}`)}>
                  <td>{fmtDateTime(r.created_at)}</td><td><UserChip user={r.user} id={r.user_id} /></td><td>{profileLabel(r.profile)}{r.prefer_shade && <small className="adm-muted"> · 그늘</small>}</td>
                  <td className="wrap">{r.origin.name || '?'} → {r.destination.name || '?'}</td><td><Status value={r.status} /></td>
                  <td>{r.n_results ?? '–'}</td><td><Rank rank={r.chosen_rank} /></td>
                  <td>{r.personalized ? (r.explored ? '탐험' : '적용') : <span className="adm-muted">–</span>}</td>
                  <td><Chips items={r.weather_flags} map={flagLabel} /></td><td>{fmtMs(r.elapsed_ms)}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={10} className="adm-muted">조건에 맞는 요청이 없어요</td></tr>}
            </Table>
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Loading>
    </Card>
  )
}

export function AccessLog() {
  const [kind, setKind] = useState('')
  const [path, setPath] = useState('')
  const [statusMin, setStatusMin] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const { page, setPage, reset } = usePage()
  const { data, loading, error } = useFetch(() => fetchAccess({ page, size: 50, kind, path, status_min: statusMin || undefined, from, to }), [page, kind, path, statusMin, from, to])
  return (
    <Card title="접근·인증 로그" actions={<ExportLink kind="access" />}>
      <Filters onReset={() => { setKind(''); setPath(''); setStatusMin(''); setFrom(''); setTo(''); reset() }}>
        <Select label="종류" value={kind} onChange={(v) => { setKind(v); reset() }} options={[{ value: '', label: '전체' }, { value: 'api', label: 'API' }, { value: 'auth', label: '인증' }, { value: 'admin', label: '관리자' }]} />
        <Input label="경로 (접두)" value={path} onChange={(v) => { setPath(v); reset() }} placeholder="/api/route" />
        <Select label="상태 코드" value={statusMin} onChange={(v) => { setStatusMin(v); reset() }} options={[{ value: '', label: '전체' }, { value: '400', label: '400 이상' }, { value: '500', label: '500 이상' }]} />
        <Input label="시작일" type="date" value={from} onChange={(v) => { setFrom(v); reset() }} />
        <Input label="종료일" type="date" value={to} onChange={(v) => { setTo(v); reset() }} />
      </Filters>
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <Table head={['시각', '종류', '메서드', '경로', '상태', '응답', '사용자', 'IP', '내용']}>
              {data.items.map((a) => (
                <tr key={a.id}>
                  <td>{fmtDateTime(a.created_at)}</td><td>{KIND_LABEL[a.kind] ?? a.kind}</td><td className="adm-mono">{a.method}</td><td className="adm-mono">{a.path}</td>
                  <td><HttpStatus code={a.status} /></td><td>{fmtMs(a.duration_ms)}</td><td><UserChip user={a.user} id={a.user_id} /></td>
                  <td className="adm-mono">{a.ip}</td><td className="adm-mono wrap" title={a.user_agent}>{a.detail ?? ''}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={9} className="adm-muted">기록이 없어요</td></tr>}
            </Table>
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Loading>
    </Card>
  )
}

export function EngineLog() {
  const [profile, setProfile] = useState('')
  const { page, setPage, reset } = usePage()
  const nav = useNavigate()
  const { data, loading, error } = useFetch(() => fetchEngineLogs({ page, size: 50, profile }), [page, profile])
  return (
    <Card title="엔진 성능 로그" actions={<ExportLink kind="engine" />}>
      <Filters onReset={() => { setProfile(''); reset() }}>
        <Select label="프로필" value={profile} onChange={(v) => { setProfile(v); reset() }} options={PROFILE_OPTIONS} />
      </Filters>
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <Table head={['시각', '프로필', '경로', '회랑 (노드/엣지/차단)', 'ACO 반복', '개미 성공/실패', '종료', 'GA 세대', '보관', '엔진', '백엔드', '그늘']}>
              {data.items.map((r) => (
                <tr key={r.id} className="is-click" onClick={() => nav(`/admin/logs/requests/${r.request_id}`)}>
                  <td>{fmtDateTime(r.created_at)}</td><td>{profileLabel(r.profile)}</td><td className="wrap">{r.origin_name || '?'} → {r.dest_name || '?'}</td>
                  <td>{fmtNum(r.corridor_nodes)} / {fmtNum(r.corridor_edges)} / {fmtNum(r.blocked_edges)}</td>
                  <td>{r.aco.iterations}</td><td>{r.aco.ants_completed} / {r.aco.ants_failed}</td><td className="adm-mono">{r.aco.stopped_by}</td>
                  <td>{r.ga.enabled ? r.ga.generations : '–'}</td><td>{fmtNum(r.archive_size)}</td><td>{fmtMs(r.engine_elapsed_ms)}</td><td>{fmtMs(r.backend_elapsed_ms)}</td>
                  <td className="adm-mono">{r.shade_status}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={12} className="adm-muted">기록이 없어요</td></tr>}
            </Table>
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Loading>
    </Card>
  )
}

export function ChoicesLog() {
  const [learned, setLearned] = useState('')
  const { page, setPage, reset } = usePage()
  const nav = useNavigate()
  const { data, loading, error } = useFetch(() => fetchChoices({ page, size: 50, learned: learned === '' ? undefined : learned === 'true' }), [page, learned])
  return (
    <Card title="경로 선택 로그" actions={<ExportLink kind="choices" />}>
      <Filters onReset={() => { setLearned(''); reset() }}>
        <Select label="학습 반영" value={learned} onChange={(v) => { setLearned(v); reset() }} options={[{ value: '', label: '전체' }, { value: 'true', label: '반영됨' }, { value: 'false', label: '미반영' }]} />
      </Filters>
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <Table head={['시각', '사용자', '프로필', '경로', '고른 순위', '제시 방식', '선택 확률', '학습']}>
              {data.items.map((c) => (
                <tr key={c.id} className="is-click" onClick={() => nav(`/admin/logs/requests/${c.request_id}`)}>
                  <td>{fmtDateTime(c.created_at)}</td><td><UserChip user={c.user} id={c.user_id} /></td><td>{profileLabel(c.profile)}</td>
                  <td className="wrap">{c.origin_name || '?'} → {c.dest_name || '?'}</td><td><Rank rank={c.shown_rank} /></td>
                  <td>{c.personalized ? (c.explored ? '개인화 · 탐험' : '개인화') : '엔진 순위'}</td><td>{c.propensity === null ? '–' : fmtPct(c.propensity)}</td>
                  <td>{c.learned ? '반영' : <span className="adm-muted">–</span>}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={8} className="adm-muted">기록이 없어요</td></tr>}
            </Table>
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Loading>
    </Card>
  )
}

export function PlacesLog() {
  const [q, setQ] = useState('')
  const { page, setPage, reset } = usePage()
  const { data, loading, error } = useFetch(() => fetchPlaces({ page, size: 50, q }), [page, q])
  return (
    <Card title="장소 검색 로그">
      <Filters onReset={() => { setQ(''); reset() }}>
        <Input label="검색어" value={q} onChange={(v) => { setQ(v); reset() }} placeholder="예: 부산역" />
      </Filters>
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <Table head={['시각', '검색어', '출처', '결과 수']}>
              {data.items.map((p) => (
                <tr key={p.id} className={p.result_count === 0 ? 'is-hi' : undefined}>
                  <td>{fmtDateTime(p.created_at)}</td><td className="wrap">{p.query}</td><td className="adm-mono">{p.source}</td><td>{p.result_count}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={4} className="adm-muted">기록이 없어요</td></tr>}
            </Table>
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Loading>
    </Card>
  )
}
