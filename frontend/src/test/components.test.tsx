import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import RouteCard from '../components/RouteCard'
import RouteDetail from '../components/RouteDetail'
import SchematicMap from '../components/SchematicMap'
import WeatherChip from '../components/WeatherChip'
import { response, walkRoute } from './fixtures'

describe('RouteCard', () => {
  it('renders badges, metrics and cautions', () => {
    const onSelect = vi.fn()
    render(<RouteCard route={walkRoute} selected={false} onSelect={onSelect} shadeAvailable />)
    expect(screen.getByText('1순위')).toBeInTheDocument()
    expect(screen.getByText('가장 빠른 길')).toBeInTheDocument()
    expect(screen.getByText('엘리베이터 확인됨')).toBeInTheDocument()
    expect(screen.getByText('674m')).toBeInTheDocument()
    expect(screen.getByText('12%')).toBeInTheDocument()
    expect(screen.getByText(/더위 주의/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('option'))
    fireEvent.keyDown(screen.getByRole('option'), { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledTimes(2)
  })

  it('hides shade when not computed', () => {
    render(<RouteCard route={walkRoute} selected onSelect={() => undefined} shadeAvailable={false} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

describe('RouteDetail', () => {
  it('lists legs with mode-specific meta', () => {
    render(<RouteDetail route={walkRoute} />)
    expect(screen.getByText('도보 300m · 6분')).toBeInTheDocument()
    expect(screen.getByText('엘리베이터 이용 확인됨 · 2분')).toBeInTheDocument()
    expect(screen.getByText('A역 → D역')).toBeInTheDocument()
  })
})

describe('WeatherChip', () => {
  it('shows source, flags and shade status', () => {
    render(<WeatherChip weather={response.weather} metadata={response.metadata} />)
    expect(screen.getByText(/Open-Meteo · 체감 34℃ · PM10 40/)).toBeInTheDocument()
    expect(screen.getByText('폭염')).toBeInTheDocument()
    expect(screen.getByText(/건물 그늘 계산됨 · 높이 정보 97%/)).toBeInTheDocument()
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

  it('shows a hint when nothing to draw', () => {
    render(<SchematicMap origin={null} destination={null} routes={[]} selectedId={null} overlay="mode" onSelect={() => undefined} />)
    expect(screen.getByText(/길찾기를 누르면/)).toBeInTheDocument()
  })
})
