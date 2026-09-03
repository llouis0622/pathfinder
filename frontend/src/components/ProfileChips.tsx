import { PROFILE_SHORT } from '../lib/format'
import type { Profile, ProfileId } from '../types'

type Props = {
  profiles: Profile[]
  selected: ProfileId
  onSelect: (id: ProfileId) => void
  preferShade: boolean
  onToggleShade: () => void
}

export default function ProfileChips({ profiles, selected, onSelect, preferShade, onToggleShade }: Props) {
  return (
    <div className="chips" role="group" aria-label="이용자 유형과 선호">
      <div className="chips__row" role="radiogroup" aria-label="이용자 유형">
        {profiles.map((p) => (
          <button key={p.id} type="button" role="radio" aria-checked={selected === p.id}
            className={`chip${selected === p.id ? ' is-on' : ''}`} onClick={() => onSelect(p.id)}>
            {PROFILE_SHORT[p.id] ?? p.label}
          </button>
        ))}
      </div>
      <button type="button" className={`chip chip--toggle${preferShade ? ' is-on' : ''}`} aria-pressed={preferShade} onClick={onToggleShade}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
        그늘 우선
      </button>
    </div>
  )
}
