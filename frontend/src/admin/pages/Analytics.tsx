import { useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { fetchEngineStats, fetchIps, fetchQuality, fetchSpatial, fetchUsage } from '../api'
import { BarChart, LineChart, RankBars, SERIES, ShareBar, StatTile, fmtMs, fmtNum, fmtPct, shortDates } from '../charts'
import { Card, DaysPicker, Loading, STATUS_LABEL, Table, badgeLabel, flagLabel, useFetch } from '../ui'

export function Analytics() {
  const { tab } = useParams()
  const [days, setDays] = useState(30)
  if (tab !== 'usage' && tab !== 'quality' && tab !== 'spatial') return <Navigate to="/admin/analytics/usage" replace />
  return (
    <>
      <div className="adm__toolbar"><span className="adm-muted">최근</span><DaysPicker value={days} onChange={setDays} /></div>
      {tab === 'usage' && <Usage days={days} />}
      {tab === 'quality' && <Quality days={days} />}
      {tab === 'spatial' && <Spatial days={days} />}
    </>
  )
}

function Usage({ days }: { days: number }) {
  const { data, loading, error } = useFetch(() => fetchUsage(days), [days])
  const eng = useFetch(() => fetchEngineStats(days), [days])
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          <div className="adm-grid adm-grid--tiles">
            <StatTile label={`검색 (${days}일)`} value={fmtNum(data.total_requests)} sub={`하루 평균 ${fmtNum(data.total_requests / days, 1)}`} />
            <StatTile label="경로 선택" value={fmtNum(data.daily.reduce((a, d) => a + d.choices, 0))} />
            <StatTile label="신규 사용자" value={fmtNum(data.daily.reduce((a, d) => a + d.new_users, 0))} />
            <StatTile label="장소 검색" value={fmtNum(data.place_searches.total)} sub={`결과 없음 ${fmtNum(data.place_searches.no_result)}`} />
            <StatTile label="그늘 우선 켠 비율" value={fmtPct(data.total_requests ? data.prefer_shade.on / data.total_requests : null)} />
          </div>
          <Card title="일별 검색·선택·사용자">
            <LineChart labels={shortDates(data.daily.map((d) => d.date))} series={[
              { key: 'requests', label: '검색', values: data.daily.map((d) => d.requests) },
              { key: 'choices', label: '선택', values: data.daily.map((d) => d.choices) },
              { key: 'users', label: '로그인 사용자', values: data.daily.map((d) => d.users) },
              { key: 'new', label: '신규 가입', values: data.daily.map((d) => d.new_users) },
            ]} />
          </Card>
          <div className="adm-grid adm-grid--2">
            <Card title="시간대별 검색"><BarChart labels={data.hourly.map((h) => `${h.hour}시`)} values={data.hourly.map((h) => h.count)} /></Card>
            <Card title="요일별 검색"><BarChart labels={data.weekday.map((w) => w.label)} values={data.weekday.map((w) => w.count)} highlight={(i) => i >= 5} /></Card>
          </div>
          <div className="adm-grid adm-grid--3">
            <Card title="프로필 비중"><ShareBar items={data.profile_share.map((p) => ({ label: p.label, value: p.count }))} /></Card>
            <Card title="검색 결과 상태"><ShareBar items={data.status_share.map((s, i) => ({ label: STATUS_LABEL[s.status] ?? s.status, value: s.count, color: [SERIES[2], SERIES[3], SERIES[1]][i] }))} /></Card>
            <Card title="검색 시 날씨 조건"><RankBars items={data.weather_flags.map((f) => ({ label: flagLabel(f.flag), value: f.count }))} empty="특이 날씨 없음" /></Card>
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="자주 찾은 장소 검색어"><RankBars items={data.place_searches.top_queries.map((q) => ({ label: q.query, value: q.count }))} /></Card>
            <Card title="엔진 응답 시간 (일별 p50 / p95)">
              <Loading loading={eng.loading} error={eng.error}>
                {eng.data && (
                  <>
                    <div className="adm-kv" style={{ marginBottom: 12 }}>
                      <div>실행<b>{fmtNum(eng.data.summary.runs)}</b></div>
                      <div>엔진 p50 / p95<b>{fmtMs(eng.data.summary.engine_p50_ms)} / {fmtMs(eng.data.summary.engine_p95_ms)}</b></div>
                      <div>ACO / GA p50<b>{fmtMs(eng.data.summary.aco_p50_ms)} / {fmtMs(eng.data.summary.ga_p50_ms)}</b></div>
                      <div>평균 반복 / 세대<b>{fmtNum(eng.data.summary.avg_iterations, 1)} / {fmtNum(eng.data.summary.avg_generations, 1)}</b></div>
                      <div>개미 실패율<b>{fmtPct(eng.data.summary.ant_fail_ratio)}</b></div>
                      <div>평균 회랑 노드<b>{fmtNum(eng.data.summary.avg_corridor_nodes)}</b></div>
                    </div>
                    <LineChart height={180} labels={shortDates(eng.data.daily.map((d) => d.date))} format={(v) => fmtMs(v)} series={[
                      { key: 'p50', label: 'p50', values: eng.data.daily.map((d) => d.p50_ms) },
                      { key: 'p95', label: 'p95', values: eng.data.daily.map((d) => d.p95_ms) },
                    ]} />
                  </>
                )}
              </Loading>
            </Card>
          </div>
        </>
      )}
    </Loading>
  )
}

function IpsCard({ days }: { days: number }) {
  const { data, loading, error } = useFetch(() => fetchIps(days), [days])
  return (
    <Card title="오프라인 평가 (IPS · 역확률 가중)">
      <Loading loading={loading} error={error}>
        {data && (
          <>
            <div className="adm-kv" style={{ marginBottom: 12 }}>
              <div>표본 (개인화 검색 중 선택)<b>{fmtNum(data.samples)}</b></div>
              <div>탐험 표본<b>{fmtNum(data.explored ?? 0)}</b></div>
              <div>로깅 1순위 적중률<b>{fmtPct(data.logged_hit_rate ?? null)}</b></div>
              <div>ε<b>{data.epsilon}</b></div>
            </div>
            <Table head={['정책', '일치 표본', 'IPS', 'SNIPS', '유효 표본 수']}>
              {(['personalized', 'engine'] as const).map((k) => data.policies[k] && (
                <tr key={k}><td>{k === 'engine' ? '엔진 순위' : '개인화 (탐욕)'}</td><td>{fmtNum(data.policies[k]!.matched)}</td><td>{fmtPct(data.policies[k]!.ips)}</td><td>{fmtPct(data.policies[k]!.snips)}</td><td>{fmtNum(data.policies[k]!.ess, 1)}</td></tr>
              ))}
              {data.samples === 0 && <tr><td colSpan={5} className="adm-muted">아직 표본이 없어요</td></tr>}
            </Table>
            {data.note && <p className="adm-muted" style={{ marginTop: 10, fontSize: 13 }}>{data.note}</p>}
          </>
        )}
      </Loading>
    </Card>
  )
}

function Quality({ days }: { days: number }) {
  const { data, loading, error } = useFetch(() => fetchQuality(days), [days])
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          <div className="adm-grid adm-grid--tiles">
            <StatTile label="경로 선택률" value={fmtPct(data.choose_rate)} sub={`성공 ${fmtNum(data.ok)}건 중 ${fmtNum(data.choices)}건 선택`} />
            <StatTile label="학습에 반영된 선택" value={fmtNum(data.learned_choices)} />
            <StatTile label="1순위 적중률 · 엔진 순위" value={fmtPct(data.compare.plain.rank1_hit_rate)} sub={`${fmtNum(data.compare.plain.choices)}건`} />
            <StatTile label="1순위 적중률 · 개인화" value={fmtPct(data.compare.personalized.rank1_hit_rate)} sub={`${fmtNum(data.compare.personalized.choices)}건`}
              tone={(data.compare.personalized.rank1_hit_rate ?? 0) > (data.compare.plain.rank1_hit_rate ?? 0) && data.compare.personalized.choices > 0 ? 'good' : undefined} />
            <StatTile label="탐험 제시 중 1순위 선택" value={fmtPct(data.compare.explored.rank1_hit_rate)} sub={`${fmtNum(data.compare.explored.choices)}건`} />
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="제시 순위별 선택률"><RankBars items={data.by_shown_rank.map((r) => ({ label: `${r.rank}순위`, value: r.rate ?? 0, sub: `${r.chosen}/${r.shown}` }))} format={(v) => fmtPct(v)} max={1} /></Card>
            <Card title="엔진 순위별 선택률 (개인화 전 순위 기준)"><RankBars items={data.by_engine_rank.map((r) => ({ label: `엔진 ${r.rank}순위`, value: r.rate ?? 0, sub: `${r.chosen}/${r.shown}` }))} format={(v) => fmtPct(v)} max={1} color={SERIES[1]} /></Card>
          </div>
          <Card title="프로필별 품질 (1순위 경로 기준)">
            <Table head={['프로필', '검색', '경로 없음', '평균 응답', '평균 소요', '평균 도보', '평균 환승']}>
              {data.per_profile.map((p) => (
                <tr key={p.profile}>
                  <td>{p.label}</td><td>{fmtNum(p.requests)}</td><td>{fmtPct(p.no_route_rate)}</td><td>{fmtMs(p.avg_elapsed_ms)}</td>
                  <td>{p.avg_duration_min === null ? '–' : `${fmtNum(p.avg_duration_min, 1)}분`}</td><td>{p.avg_walk_m === null ? '–' : `${fmtNum(p.avg_walk_m)}m`}</td><td>{fmtNum(p.avg_transfers, 2)}</td>
                </tr>
              ))}
              {data.per_profile.length === 0 && <tr><td colSpan={7} className="adm-muted">데이터 없음</td></tr>}
            </Table>
          </Card>
          <IpsCard days={days} />
          <div className="adm-grid adm-grid--2">
            <Card title="자주 붙은 배지"><RankBars items={data.badges.map((b) => ({ label: badgeLabel(b.key), value: b.count }))} color={SERIES[2]} /></Card>
            <Card title="자주 나온 주의 사항"><RankBars items={data.cautions.map((c) => ({ label: c.key, value: c.count }))} color={SERIES[3]} empty="주의 사항 없음" /></Card>
          </div>
        </>
      )}
    </Loading>
  )
}

function Spatial({ days }: { days: number }) {
  const { data, loading, error } = useFetch(() => fetchSpatial(days), [days])
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          <div className="adm-grid adm-grid--2">
            <Card title="인기 출발지"><RankBars items={data.top_origins.map((p) => ({ label: p.name, value: p.count, sub: `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}` }))} /></Card>
            <Card title="인기 도착지"><RankBars items={data.top_destinations.map((p) => ({ label: p.name, value: p.count, sub: `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}` }))} color={SERIES[1]} /></Card>
          </div>
          <Card title="자주 찾는 출발 → 도착">
            <Table head={['출발', '도착', '검색', '경로 없음']}>
              {data.top_pairs.map((p) => (
                <tr key={`${p.origin}→${p.destination}`} className={p.no_route > 0 ? 'is-hi' : undefined}><td className="wrap">{p.origin}</td><td className="wrap">{p.destination}</td><td>{fmtNum(p.count)}</td><td>{p.no_route ? fmtNum(p.no_route) : '–'}</td></tr>
              ))}
              {data.top_pairs.length === 0 && <tr><td colSpan={4} className="adm-muted">데이터 없음</td></tr>}
            </Table>
          </Card>
          <div className="adm-grid adm-grid--3">
            <Card title="많이 지나는 역·정류장"><RankBars items={data.top_stations.map((s) => ({ label: s.name, value: s.count }))} color={SERIES[2]} /></Card>
            <Card title="이용 노선"><RankBars items={data.lines.map((l) => ({ label: l.name, value: l.count }))} color={SERIES[3]} /></Card>
            <div className="adm-grid" style={{ gap: 16 }}>
              <Card title="수직 이동 시설"><ShareBar items={data.facilities.map((f) => ({ label: f.facility, value: f.count }))} /></Card>
              <Card title="미확인 엘리베이터가 포함된 역"><RankBars items={data.unverified_stations.map((s) => ({ label: s.name, value: s.count }))} color={SERIES[1]} empty="모두 확인된 시설" /></Card>
            </div>
          </div>
        </>
      )}
    </Loading>
  )
}
