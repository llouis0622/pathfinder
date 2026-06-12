import type { UserProfile } from '../../types'

// 프로필별 기본 가중치 정의
export const USER_PROFILES: UserProfile[] = [
  {
    id: 'general',
    label: '일반',
    weights: {
      avoid_stairs: false, elevator_priority: false, low_grade: false,
      min_transfer: false, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: false, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'wheelchair',
    label: '휠체어',
    weights: {
      avoid_stairs: true, elevator_priority: true, low_grade: true,
      min_transfer: false, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: false, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'stroller',
    label: '유모차',
    weights: {
      avoid_stairs: true, elevator_priority: true, low_grade: false,
      min_transfer: false, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: false, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'elderly',
    label: '고령자',
    weights: {
      avoid_stairs: false, elevator_priority: false, low_grade: true,
      min_transfer: true, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: true, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'pregnant',
    label: '임산부',
    weights: {
      avoid_stairs: false, elevator_priority: false, low_grade: false,
      min_transfer: true, avoid_crowded: true, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: true, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'visually_impaired',
    label: '시각약자',
    weights: {
      avoid_stairs: true, elevator_priority: false, low_grade: false,
      min_transfer: false, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: false, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'injured',
    label: '부상자',
    weights: {
      avoid_stairs: true, elevator_priority: true, low_grade: false,
      min_transfer: true, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: true, avoid_heat: false, avoid_cold: false,
    },
  },
  {
    id: 'heat_sensitive',
    label: '더위취약',
    weights: {
      avoid_stairs: false, elevator_priority: false, low_grade: false,
      min_transfer: false, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: false, avoid_heat: true, avoid_cold: false,
    },
  },
  {
    id: 'cold_sensitive',
    label: '추위취약',
    weights: {
      avoid_stairs: false, elevator_priority: false, low_grade: false,
      min_transfer: false, avoid_crowded: false, wide_sidewalk: false,
      shelter_nearby: false, low_walk_distance: false, avoid_heat: false, avoid_cold: true,
    },
  },
]

type Props = {
  selectedId: string
  onSelect: (profile: UserProfile) => void
}

// 사용자 프로필 선택 버튼 그룹
export default function ProfileSelector({ selectedId, onSelect }: Props) {
  return (
    <div style={styles.row}>
      {USER_PROFILES.map((profile) => (
        <button
          key={profile.id}
          style={{
            ...styles.btn,
            ...(selectedId === profile.id ? styles.btnActive : {}),
          }}
          onClick={() => onSelect(profile)}
        >
          {profile.label}
        </button>
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  row: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    padding: '8px 16px',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
  },
  btn: {
    padding: '5px 12px',
    border: '1px solid #d1d5db',
    borderRadius: 20,
    background: '#fff',
    fontSize: 13,
    cursor: 'pointer',
    color: '#374151',
  },
  btnActive: {
    background: '#2563eb',
    color: '#fff',
    border: '1px solid #2563eb',
  },
}
