import { PROFILE_SHORT } from '../lib/format'
import type { Profile, ProfileId } from '../types'

type Props = {
  profiles: Profile[]
  selected: ProfileId
  onSelect: (id: ProfileId) => void
  preferShade: boolean
  onToggleShade: () => void
}

const HELP: Record<ProfileId, string> = {
  wheelchair: '계단·급경사·좁은 보도·턱을 피하고 엘리베이터와 저상버스만 이용해요',
  elderly: '계단과 급경사 부담을 줄이고 도보를 짧게, 폭염·한파에 민감하게 봐요',
  walking_aid: '보행보조기·목발. 계단 부담을 더 크게 보고 엘리베이터를 우선해요',
  visually_impaired: '신호 없는 횡단을 피하고 점자블록·난간이 있는 길을 우선해요',
}

export default function ProfileChips({ profiles, selected, onSelect, preferShade, onToggleShade }: Props) {
  const current = profiles.find((p) => p.id === selected)
  const help = current?.description || HELP[selected]
  return (
    <div className="chips" role="group" aria-label="이용자 유형과 선호">
      <div className="chips__row" role="radiogroup" aria-label="이용자 유형" aria-describedby="profile-help">
        {profiles.map((p) => (
          <button key={p.id} type="button" role="radio" aria-checked={selected === p.id} title={p.description || HELP[p.id]}
            className={`chip${selected === p.id ? ' is-on' : ''}`} onClick={() => onSelect(p.id)}>
            {PROFILE_SHORT[p.id] ?? p.label}
          </button>
        ))}
      </div>
      <button type="button" className={`chip chip--toggle${preferShade ? ' is-on' : ''}`} aria-pressed={preferShade} onClick={onToggleShade}
        title="켜면 날씨와 상관없이 그늘이 많은 보행 구간을 우선해요">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
        그늘 우선
      </button>
      <p id="profile-help" className="chips__help">{help}</p>
    </div>
  )
}
