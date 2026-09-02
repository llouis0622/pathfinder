import type { Profile, ProfileId } from '../types'

type Props = {
  profiles: Profile[]
  selected: ProfileId
  onSelect: (id: ProfileId) => void
}

const ICONS: Record<ProfileId, string> = { wheelchair: '♿', elderly: '🧓', walking_aid: '🦯', visually_impaired: '👁️' }

export default function ProfileSelector({ profiles, selected, onSelect }: Props) {
  const current = profiles.find((p) => p.id === selected)
  return (
    <fieldset className="profiles">
      <legend className="section__title">이용자 프로필</legend>
      <div className="profiles__grid" role="radiogroup" aria-label="이용자 프로필">
        {profiles.map((p) => (
          <button key={p.id} type="button" role="radio" aria-checked={selected === p.id}
            className={`profile${selected === p.id ? ' is-selected' : ''}`} onClick={() => onSelect(p.id)}>
            <span className="profile__icon" aria-hidden="true">{ICONS[p.id]}</span>
            <span className="profile__label">{p.label}</span>
          </button>
        ))}
      </div>
      {current?.description && <p className="profiles__desc">{current.description}</p>}
    </fieldset>
  )
}
