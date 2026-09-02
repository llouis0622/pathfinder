import { WEATHER_FLAG_LABELS } from '../lib/format'
import type { SearchMetadata, Weather } from '../types'

type Props = { weather: Weather; metadata: SearchMetadata }

const SHADE_LABEL: Record<string, string> = {
  computed: '건물 그늘 계산됨',
  not_daylight: '야간 (그늘 계산 없음)',
  no_buildings: '건물 정보 없음',
  disabled: '출발 시각 없음',
}

export default function WeatherChip({ weather, metadata }: Props) {
  const temp = weather.feels_like_c ?? weather.temp_c
  const source: Record<string, string> = { open_meteo: 'Open-Meteo', openweather: 'OpenWeather', manual: '직접 지정', none: '미반영', unavailable: '조회 실패' }
  return (
    <div className="status" aria-live="polite">
      <div className="status__row">
        <span className="status__key">날씨</span>
        <span>
          {source[weather.source] ?? weather.source}
          {temp !== null && temp !== undefined ? ` · 체감 ${temp.toFixed(0)}℃` : ''}
          {weather.pm10 !== null && weather.pm10 !== undefined ? ` · PM10 ${Math.round(weather.pm10)}` : ''}
        </span>
      </div>
      {weather.flags.length > 0 && (
        <div className="status__row">
          <span className="status__key">반영</span>
          <span className="chips chips--static">{weather.flags.map((f) => <span key={f} className="chip is-on">{WEATHER_FLAG_LABELS[f] ?? f}</span>)}</span>
        </div>
      )}
      {weather.note && <div className="status__note">{weather.note}</div>}
      <div className="status__row">
        <span className="status__key">그늘</span>
        <span>{SHADE_LABEL[metadata.shade_status] ?? metadata.shade_status}{metadata.shade_status === 'computed' && metadata.building_height_coverage !== null ? ` · 높이 정보 ${Math.round(metadata.building_height_coverage * 100)}%` : ''}</span>
      </div>
      <div className="status__row status__row--muted">
        <span className="status__key">탐색</span>
        <span>회랑 {metadata.corridor_nodes.toLocaleString()}노드 · 차단 {metadata.blocked_edges} · 후보 {metadata.archive_size} · {Math.round(metadata.elapsed_ms)}ms · 경사는 {metadata.elevation_resolution_m}m 지형 추정</span>
      </div>
    </div>
  )
}
