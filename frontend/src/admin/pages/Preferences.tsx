import { useNavigate } from 'react-router-dom'
import { fetchPreferencesAll } from '../api'
import { BarChart, DivergingBars, RankBars, StatTile, fmtNum } from '../charts'
import { Card, Loading, Table, UserChip, fmtDateTime, useFetch } from '../ui'

/** 백엔드 personalization.FEATURE_LABELS 와 같은 순서·의미. (양의 가중치, 음의 가중치) */
export const FEATURE_LABELS: Record<string, [string, string]> = {
  duration: ['오래 걸려도 괜찮음', '빠른 길 선호'],
  walk: ['도보 많아도 괜찮음', '도보 적은 길 선호'],
  transfers: ['환승 많아도 괜찮음', '환승 적은 길 선호'],
  grade: ['경사 있어도 괜찮음', '완만한 길 선호'],
  stairs: ['계단 있어도 괜찮음', '계단 없는 길 선호'],
  shade: ['그늘 많은 길 선호', '그늘 신경 안 씀'],
  unshaded: ['볕 걷기 괜찮음', '볕 걷기 피함'],
  unverified: ['미확인 엘리베이터 괜찮음', '확인된 엘리베이터 선호'],
  wait: ['대기 괜찮음', '대기 짧은 길 선호'],
  ride_share: ['대중교통 위주 선호', '도보 위주 선호'],
}

export default function PreferencesPage() {
  const { data, loading, error } = useFetch(fetchPreferencesAll, [])
  const nav = useNavigate()
  return (
    <Loading loading={loading} error={error}>
      {data && (
        <>
          <div className="adm-grid adm-grid--tiles">
            <StatTile label="학습된 사용자" value={fmtNum(data.learned_users)} sub={`정책 보유 ${fmtNum(data.total_policies)}명`} />
            <StatTile label="가장 흔한 취향" value={data.labels[0]?.label ?? '–'} sub={data.labels[0] ? `${data.labels[0].count}명` : '아직 없음'} />
          </div>
          <div className="adm-grid adm-grid--2">
            <Card title="특성별 평균 가중치 (모든 학습 사용자)">
              <DivergingBars max={1.5} items={data.per_feature.map((f) => ({
                key: f.feature, label: f.feature, value: f.mean, negativeLabel: f.negative_label, positiveLabel: f.positive_label,
                sub: `+${f.positive_users} / −${f.negative_users}명`,
              }))} />
            </Card>
            <div className="adm-grid" style={{ gap: 16 }}>
              <Card title="취향 요약 분포"><RankBars items={data.labels.map((l) => ({ label: l.label, value: l.count }))} format={(v) => `${fmtNum(v)}명`} empty="아직 학습된 사용자가 없어요" /></Card>
              <Card title="학습 횟수 분포"><BarChart height={160} labels={data.updates_histogram.map((h) => h.bucket)} values={data.updates_histogram.map((h) => h.count)} format={(v) => `${fmtNum(v)}명`} /></Card>
            </div>
          </div>
          <Card title="사용자별 학습된 취향">
            <Table head={['사용자', '학습', '요약', '갱신', ...Object.keys(FEATURE_LABELS)]}>
              {data.users.map((u) => (
                <tr key={u.user.id} className="is-click" onClick={() => nav(`/admin/users/${u.user.id}`)}>
                  <td><UserChip user={u.user} /></td><td>{u.updates}</td><td className="wrap">{u.summary.join(' · ') || '–'}</td><td>{fmtDateTime(u.updated_at)}</td>
                  {Object.keys(FEATURE_LABELS).map((f) => <td key={f} className={Math.abs(u.weights[f] ?? 0) >= 0.25 ? '' : 'adm-muted'}>{(u.weights[f] ?? 0).toFixed(2)}</td>)}
                </tr>
              ))}
              {data.users.length === 0 && <tr><td colSpan={14} className="adm-muted">아직 학습된 사용자가 없어요</td></tr>}
            </Table>
          </Card>
        </>
      )}
    </Loading>
  )
}
