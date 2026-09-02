import { WEATHER_FLAG_LABELS } from '../lib/format'
import type { WeatherFlag, WeatherMode } from '../types'

export type Conditions = {
  departure: string            // datetime-local 값
  weatherMode: WeatherMode
  manual: Partial<Record<WeatherFlag, boolean>>
}

type Props = {
  value: Conditions
  onChange: (next: Conditions) => void
}

const MANUAL_FLAGS: WeatherFlag[] = ['heatwave', 'heat', 'coldwave', 'cold', 'rain', 'bad_air', 'windy']

export default function ConditionsPanel({ value, onChange }: Props) {
  return (
    <div className="conditions">
      <h2 className="section__title">출발 조건</h2>
      <label className="field">
        <span className="field__label">출발 시각 (그늘·예보 계산 기준)</span>
        <input type="datetime-local" className="field__input" value={value.departure}
          onChange={(e) => onChange({ ...value, departure: e.target.value })} />
      </label>
      <div className="field">
        <span className="field__label">날씨 반영</span>
        <div className="segmented" role="radiogroup" aria-label="날씨 반영 방식">
          {([['auto', '자동(예보)'], ['manual', '직접 지정'], ['none', '반영 안 함']] as [WeatherMode, string][]).map(([mode, label]) => (
            <button key={mode} type="button" role="radio" aria-checked={value.weatherMode === mode}
              className={`segmented__item${value.weatherMode === mode ? ' is-selected' : ''}`}
              onClick={() => onChange({ ...value, weatherMode: mode })}>{label}</button>
          ))}
        </div>
      </div>
      {value.weatherMode === 'manual' && (
        <div className="chips" aria-label="날씨 조건">
          {MANUAL_FLAGS.map((f) => (
            <button key={f} type="button" className={`chip${value.manual[f] ? ' is-on' : ''}`} aria-pressed={!!value.manual[f]}
              onClick={() => onChange({ ...value, manual: { ...value.manual, [f]: !value.manual[f] } })}>
              {WEATHER_FLAG_LABELS[f]}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
