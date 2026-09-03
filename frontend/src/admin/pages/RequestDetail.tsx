import { Link, useParams } from 'react-router-dom'
import SchematicMap from '../../components/SchematicMap'
import { formatDistance } from '../../lib/format'
import type { Place } from '../../types'
import { fetchRequestDetail } from '../api'
import { DivergingBars, fmtMs, fmtNum, fmtPct } from '../charts'
import { Card, Chips, Json, Loading, Rank, Status, Table, UserChip, badgeLabel, flagLabel, fmtDateTime, profileLabel, useFetch } from '../ui'
import { FEATURE_LABELS } from './Preferences'

export default function RequestDetailPage() {
  const { id = '' } = useParams()
  const { data, loading, error } = useFetch(() => fetchRequestDetail(id), [id])
  return (
    <Loading loading={loading} error={error}>
      {data && <Detail data={data} />}
    </Loading>
  )
}

function Detail({ data }: { data: NonNullable<ReturnType<typeof useFetch<Awaited<ReturnType<typeof fetchRequestDetail>>>>['data']> }) {
  const r = data.request
  const origin: Place = { id: 'o', name: r.origin.name, address: '', lat: r.origin.lat, lng: r.origin.lng, category: '', source: '' }
  const destination: Place = { id: 'd', name: r.destination.name, address: '', lat: r.destination.lat, lng: r.destination.lng, category: '', source: '' }
  const routes = data.routes.map((x) => x.payload)
  const chosenRank = data.choice?.shown_rank ?? null
  const selectedId = routes.find((x) => x.rank === (chosenRank ?? 1))?.id ?? routes[0]?.id ?? null
  const weights = data.policy_update
  return (
    <>
      <div className="adm__toolbar">
        <Link className="adm-btn adm-btn--ghost" to="/admin/logs/requests">← 목록</Link>
        <span className="adm-mono">{r.id}</span>
      </div>
      <div className="adm-grid adm-grid--2">
        <Card title="요청">
          <div className="adm-kv">
            <div>시각<b>{fmtDateTime(r.created_at)}</b></div>
            <div>사용자<b><UserChip user={r.user} id={r.user_id} /></b></div>
            <div>프로필<b>{profileLabel(r.profile)}{r.prefer_shade ? ' · 그늘 우선' : ''}</b></div>
            <div>상태<b><Status value={r.status} /></b></div>
            <div>출발<b>{r.origin.name || '이름 없음'}<small className="adm-muted"> {r.origin.lat.toFixed(5)}, {r.origin.lng.toFixed(5)}</small></b></div>
            <div>도착<b>{r.destination.name || '이름 없음'}<small className="adm-muted"> {r.destination.lat.toFixed(5)}, {r.destination.lng.toFixed(5)}</small></b></div>
            <div>출발 시각<b>{fmtDateTime(r.departure_at)}</b></div>
            <div>응답 시간<b>{fmtMs(r.elapsed_ms)}</b></div>
            <div>개인화<b>{r.personalized ? (r.explored ? '적용 (탐험)' : '적용') : '미적용'}</b></div>
            <div>날씨<b><Chips items={r.weather_flags} map={flagLabel} /></b></div>
            <div>선택<b><Rank rank={chosenRank} /></b></div>
          </div>
          {r.error && <div className="adm-error" style={{ marginTop: 12 }}>{r.error}</div>}
          <div style={{ marginTop: 12 }}><Json value={{ weather: data.weather, options: data.options, propensities: data.propensities, metadata: data.metadata }} /></div>
        </Card>
        <Card title="지도">
          <div className="adm-map">
            <SchematicMap origin={origin} destination={destination} routes={routes} selectedId={selectedId} overlay="mode" onSelect={() => undefined} />
          </div>
        </Card>
      </div>
      <Card title="제시된 경로">
        <Table head={['순위', '엔진 순위', '요약', '소요', '도보', '환승', '일반화 비용', '배지', '주의', '알고리즘']}>
          {data.routes.map((x) => (
            <tr key={x.rank} className={x.rank === chosenRank ? 'is-hi' : undefined}>
              <td><Rank rank={x.rank} /></td><td>{x.engine_rank ?? '–'}</td><td className="wrap">{x.summary}</td><td>{fmtNum(x.total_duration_min)}분</td>
              <td>{formatDistance(x.walk_distance_m)}</td><td>{x.transfers}</td><td>{x.generalized_cost_s === null ? '–' : `${fmtNum(x.generalized_cost_s)}s`}</td>
              <td><Chips items={x.badges} map={badgeLabel} /></td><td className="wrap"><Chips items={x.cautions} /></td>
              <td className="adm-mono">{x.payload.origin_algorithm ?? ''}</td>
            </tr>
          ))}
        </Table>
      </Card>
      <div className="adm-grid adm-grid--2">
        <Card title="엔진 실행">
          {data.engine_run ? (
            <div className="adm-kv">
              <div>회랑 노드/엣지<b>{fmtNum(data.engine_run.corridor_nodes)} / {fmtNum(data.engine_run.corridor_edges)}</b></div>
              <div>차단 엣지<b>{fmtNum(data.engine_run.blocked_edges)}</b></div>
              <div>스냅 거리<b>{data.engine_run.snap_origin_m?.toFixed(0) ?? '–'}m / {data.engine_run.snap_destination_m?.toFixed(0) ?? '–'}m</b></div>
              <div>ACO 반복<b>{data.engine_run.aco.iterations} <small className="adm-muted">({data.engine_run.aco.stopped_by})</small></b></div>
              <div>개미 성공/실패<b>{data.engine_run.aco.ants_completed} / {data.engine_run.aco.ants_failed}</b></div>
              <div>ACO 시간<b>{fmtMs(data.engine_run.aco.elapsed_ms)}</b></div>
              <div>GA 세대<b>{data.engine_run.ga.enabled ? data.engine_run.ga.generations : '꺼짐'}</b></div>
              <div>GA 시간<b>{fmtMs(data.engine_run.ga.elapsed_ms)}</b></div>
              <div>보관 경로<b>{fmtNum(data.engine_run.archive_size)}</b></div>
              <div>엔진 / 백엔드<b>{fmtMs(data.engine_run.engine_elapsed_ms)} / {fmtMs(data.engine_run.backend_elapsed_ms)}</b></div>
              <div>그늘 계산<b className="adm-mono">{data.engine_run.shade_status || '–'}</b></div>
            </div>
          ) : <div className="adm-empty">엔진 실행 기록이 없어요</div>}
        </Card>
        <Card title="개인화 갱신">
          {weights ? (
            <>
              <div className="adm-kv" style={{ marginBottom: 12 }}>
                <div>고른 순위<b>{weights.shown_rank}순위 <small className="adm-muted">(엔진 {weights.engine_rank ?? '–'}순위)</small></b></div>
                <div>누적 학습<b>{weights.updates_after}회</b></div>
                <div>제시 방식<b>{weights.explored ? '탐험' : '정책'}</b></div>
              </div>
              <DivergingBars title="가중치 변화 (이번 선택으로 움직인 양)" items={Object.keys(FEATURE_LABELS).map((f) => ({
                key: f, label: f, value: (weights.weights_after[f] ?? 0) - (weights.weights_before[f] ?? 0),
                negativeLabel: FEATURE_LABELS[f][1], positiveLabel: FEATURE_LABELS[f][0],
              }))} format={(v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2))} />
            </>
          ) : (
            <div className="adm-empty">{data.choice ? (data.choice.user ? '학습 조건을 채우지 못했어요 (후보 2개 미만 등)' : `게스트 선택 · ${fmtPct(data.choice.propensity)}`) : '아직 선택하지 않았어요'}</div>
          )}
        </Card>
      </div>
    </>
  )
}
