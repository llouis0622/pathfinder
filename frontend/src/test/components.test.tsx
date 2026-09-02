import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ProfileChips from '../components/ProfileChips'
import RouteDetail from '../components/RouteDetail'
import RouteRow from '../components/RouteRow'
import SchematicMap from '../components/SchematicMap'
import { PROFILE_FALLBACK } from '../lib/format'
import { response, walkRoute } from './fixtures'

describe('RouteRow', () => {
  it('shows duration, mode bar, summary, tags and the first caution', () => {
    const onSelect = vi.fn()
    const { container } = render(<RouteRow route={walkRoute} selected={false} onSelect={onSelect} />)
    expect(screen.getByText('22')).toBeInTheDocument()
    expect(screen.getByText('추천')).toBeInTheDocument()
    expect(screen.getByText('도보 674m')).toBeInTheDocument()
    expect(screen.getByText('도보 6분 · 1호선 3정거장 · 도보 6분')).toBeInTheDocument()
    expect(screen.getByText('빠름')).toBeInTheDocument()
    expect(screen.getByText('계단 없음')).toBeInTheDocument()
    expect(screen.getByText(/더위 주의/)).toBeInTheDocument()
    expect(container.querySelectorAll('.bar__seg')).toHaveLength(3)   // 수직 이동 제외
    fireEvent.click(screen.getByRole('option'))
    fireEvent.keyDown(screen.getByRole('option'), { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledTimes(2)
  })

  it('shows transfers without a recommend badge for lower ranks', () => {
    render(<RouteRow route={response.routes[1]} selected onSelect={() => undefined} />)
    expect(screen.queryByText('추천')).not.toBeInTheDocument()
    expect(screen.getByText('환승 1회')).toBeInTheDocument()
  })
})

describe('RouteDetail', () => {
  it('renders a timeline with stations, walks and elevator warnings', () => {
    const onBack = vi.fn()
    const onChoose = vi.fn()
    render(<RouteDetail route={walkRoute} originName="집" destinationName="회사" onBack={onBack} onChoose={onChoose} />)
    fireEvent.click(screen.getByRole('button', { name: '이 경로로 가기' }))
    expect(onChoose).toHaveBeenCalled()
    expect(screen.getByText('집')).toBeInTheDocument()
    expect(screen.getByText('회사')).toBeInTheDocument()
    expect(screen.getAllByText('A역').length).toBeGreaterThan(0)
    expect(screen.getByText('1호선 · 3정거장 · 7분')).toBeInTheDocument()
    expect(screen.getByText(/300m · 경사 4%/)).toBeInTheDocument()
    expect(screen.getByText(/D역 · 엘리베이터 확인 필요/)).toHaveClass('is-warn')
    fireEvent.click(screen.getByRole('button', { name: '경로 목록으로' }))
    expect(onBack).toHaveBeenCalled()
  })
})

describe('ProfileChips', () => {
  it('selects a profile and toggles shade preference', () => {
    const onSelect = vi.fn()
    const onToggle = vi.fn()
    render(<ProfileChips profiles={PROFILE_FALLBACK} selected="wheelchair" onSelect={onSelect} preferShade={false} onToggleShade={onToggle} />)
    expect(screen.getByRole('radio', { name: '휠체어' })).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(screen.getByRole('radio', { name: '고령자' }))
    expect(onSelect).toHaveBeenCalledWith('elderly')
    fireEvent.click(screen.getByRole('button', { name: '그늘 우선' }))
    expect(onToggle).toHaveBeenCalled()
  })
})

describe('SchematicMap', () => {
  it('draws routes without a Kakao key and lets the user pick another route', () => {
    const onSelect = vi.fn()
    const { container } = render(
      <SchematicMap origin={null} destination={null} routes={response.routes} selectedId="route_1" overlay="grade" onSelect={onSelect} />,
    )
    expect(screen.getByRole('img', { name: '약식 경로 지도' })).toBeInTheDocument()
    const polylines = container.querySelectorAll('polyline')
    expect(polylines.length).toBeGreaterThan(2)
    fireEvent.click(polylines[0])
    expect(onSelect).toHaveBeenCalledWith('route_2')
  })

  it('renders an empty state when nothing to draw', () => {
    render(<SchematicMap origin={null} destination={null} routes={[]} selectedId={null} overlay="mode" onSelect={() => undefined} />)
    expect(screen.getByRole('img', { name: '지도' })).toBeInTheDocument()
  })
})
