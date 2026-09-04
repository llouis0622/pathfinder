import { Link, useNavigate } from 'react-router-dom'
import { fetchOverview, fetchSetup, type SetupItem } from '../api'
import { LineChart, ShareBar, StatTile, fmtMs, fmtNum, fmtPct, shortDates } from '../charts'
import { Card, HttpStatus, KIND_LABEL, Loading, Rank, Status, Table, UserChip, fmtDateTime, profileLabel, useFetch } from '../ui'

const LEVEL_LABEL: Record<SetupItem['level'], string> = { required: '필수', recommended: '권장', optional: '선택' }
const STATUS_LABEL: Record<SetupItem['status'], string> = { ok: '준비됨', degraded: '축소 동작', missing: '없음' }
const GUIDE_BASE = 'https://github.com/llouis0622/pathfinder/blob/main/'

/** 키·데이터가 얼마나 들어왔는지. 프론트 빌드에 들어간 VWorld 키는 서버가 모르니 여기서 덧붙인다. */
export function SetupCard() {
  const { data, loading, error } = useFetch(fetchSetup, [])
  const vworld = !!import.meta.env.VITE_VWORLD_KEY || !!import.meta.env.VITE_BASEMAP_STYLE_URL
  const items: SetupItem[] = data ? [...data.items, {
    key: 'basemap', label: '배경 지도 (VWorld)', level: 'recommended', status: vworld ? 'ok' : 'degraded', env: 'VITE_VWORLD_KEY',
    detail: vworld ? '프론트 빌드에 키가 들어 있어요' : 'OpenFreeMap(OSM) 배경으로 동작 — 국내 건물·주소 상세도가 낮아요', guide: 'docs/SETUP_GUIDE.md#5-vworld-인증키-강력-권장-배경-지도--건물-높이',
  }] : []
  const attention = items.filter((i) => i.status !== 'ok')
  const summary = data?.summary
  return (
    <Card title="설정 상태" actions={summary && (
      <span className={`adm-status adm-status--${summary.ready_for_production && attention.length === 0 ? 'ok' : summary.runnable ? 'warn' : 'error'}`}>
        {summary.ready_for_production && attention.length === 0 ? '모두 준비됨' : summary.runnable ? `${attention.length}개 항목 확인 필요` : '필수 항목 없음'}
      </span>
    )}>
      <Loading loading={loading} error={error}>
        {data && attention.length === 0 && <div className="adm-muted">필수·권장·선택 항목이 모두 채워져 있어요.</div>}
        {data && attention.length > 0 && (
          <Table head={['구분', '항목', '상태', '내용', '변수']} className="adm-table--compact">
            {attention.map((i) => (
              <tr key={i.key}>
                <td><span className={`adm-status${i.level === 'required' ? ' adm-status--error' : ''}`}>{LEVEL_LABEL[i.level]}</span></td>
                <td><b>{i.label}</b></td>
                <td><span className={`adm-status adm-status--${i.status === 'missing' ? 'error' : 'warn'}`}>{STATUS_LABEL[i.status]}</span></td>
                <td className="wrap">{i.detail}{i.guide && <> · <a className="adm-link" href={GUIDE_BASE + i.guide} target="_blank" rel="noreferrer">가이드</a></>}</td>
                <td className="adm-mono">{i.env}</td>
              </tr>
            ))}
          </Table>
        )}
        {data && <p className="adm-muted" style={{ marginTop: 10 }}>루트 <code>.env</code> 에 값을 넣고 서비스를 재시작하면 반영돼요. 터미널에서는 <code>python scripts/doctor.py</code> 로 같은 점검을 할 수 있어요.</p>}
      </Loading>
    </Card>
  )
}

export default function Dashboard() {
  const { data, loading, error } = useFetch(fetchOverview, [])
  const nav = useNavigate()
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          <SetupCard />
          <div className="adm-grid adm-grid--tiles">
            <StatTile label="오늘 검색" value={fmtNum(data.kpis.requests_today)} sub={`7일 ${fmtNum(data.kpis.requests_7d)} · 누적 ${fmtNum(data.kpis.requests_total)}`} />
            <StatTile label="활성 사용자 (7일)" value={fmtNum(data.kpis.active_users_7d)} sub={`전체 ${fmtNum(data.kpis.users_total)} · 신규 ${fmtNum(data.kpis.users_new_7d)}`} />
            <StatTile label="경로 선택률 (7일)" value={fmtPct(data.kpis.choose_rate_7d)} sub={`선택 ${fmtNum(data.kpis.choices_7d)}건`} />
            <StatTile label="개인화 적용 비율 (7일)" value={fmtPct(data.kpis.personalized_share_7d)} sub={`학습된 사용자 ${fmtNum(data.kpis.learned_users)}명`} />
            <StatTile label="경로 없음 (7일)" value={fmtPct(data.kpis.no_route_rate_7d)} tone={(data.kpis.no_route_rate_7d ?? 0) > 0.2 ? 'warn' : undefined} />
            <StatTile label="오류율 (7일)" value={fmtPct(data.kpis.error_rate_7d)} tone={(data.kpis.error_rate_7d ?? 0) > 0.05 ? 'warn' : undefined} sub={`서버 오류 24h ${fmtNum(data.kpis.access_errors_24h)}`} />
            <StatTile label="평균 응답 (7일)" value={fmtMs(data.kpis.avg_elapsed_ms_7d)} />
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="최근 30일 검색·선택·사용자">
              <LineChart labels={shortDates(data.series.map((s) => s.date))} series={[
                { key: 'requests', label: '검색', values: data.series.map((s) => s.requests) },
                { key: 'choices', label: '선택', values: data.series.map((s) => s.choices) },
                { key: 'users', label: '사용자', values: data.series.map((s) => s.users) },
              ]} />
            </Card>
            <Card title="프로필 비중 (30일)">
              <ShareBar items={data.profile_share.map((p) => ({ label: p.label, value: p.count }))} />
            </Card>
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="최근 검색" actions={<Link className="adm-link" to="/admin/logs/requests">전체 보기</Link>}>
              <Table head={['시각', '사용자', '프로필', '경로', '상태', '선택']}>
                {data.recent_requests.map((r) => (
                  <tr key={r.id} className="is-click" onClick={() => nav(`/admin/logs/requests/${r.id}`)}>
                    <td>{fmtDateTime(r.created_at)}</td><td><UserChip user={r.user} id={r.user_id} /></td><td>{profileLabel(r.profile)}</td>
                    <td className="wrap">{r.origin.name || '?'} → {r.destination.name || '?'}</td><td><Status value={r.status} /></td><td><Rank rank={r.chosen_rank} /></td>
                  </tr>
                ))}
              </Table>
            </Card>
            <Card title="최근 인증·관리자 이벤트" actions={<Link className="adm-link" to="/admin/logs/access">전체 보기</Link>}>
              <Table head={['시각', '종류', '내용', '사용자', '상태']}>
                {data.recent_auth.map((a) => (
                  <tr key={a.id}>
                    <td>{fmtDateTime(a.created_at)}</td><td>{KIND_LABEL[a.kind] ?? a.kind}</td><td className="adm-mono">{a.detail ?? a.path}</td>
                    <td><UserChip user={a.user} id={a.user_id} /></td><td><HttpStatus code={a.status} /></td>
                  </tr>
                ))}
                {data.recent_auth.length === 0 && <tr><td colSpan={5} className="adm-muted">아직 이벤트가 없어요</td></tr>}
              </Table>
            </Card>
          </div>
        </>
      )}
    </Loading>
  )
}
