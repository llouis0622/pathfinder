import { Link, useNavigate } from 'react-router-dom'
import { fetchOverview } from '../api'
import { LineChart, ShareBar, StatTile, fmtMs, fmtNum, fmtPct, shortDates } from '../charts'
import { Card, HttpStatus, KIND_LABEL, Loading, Rank, Status, Table, UserChip, fmtDateTime, profileLabel, useFetch } from '../ui'

export default function Dashboard() {
  const { data, loading, error } = useFetch(fetchOverview, [])
  const nav = useNavigate()
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
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
