/**
 * 접근성 설정(큰 글씨·고대비·음성 안내)과 음성 읽기(TTS). 설정은 브라우저에 저장되고 <html data-*> 로 반영된다.
 */
import { useCallback, useEffect, useState } from 'react'
import type { Leg, Route } from '../types'
import { formatDistance, formatMinutes, legTitle } from './format'

export type A11ySettings = { largeText: boolean; highContrast: boolean; voice: boolean }
const KEY = 'pf.a11y'
const DEFAULTS: A11ySettings = { largeText: false, highContrast: false, voice: false }

export function loadA11y(): A11ySettings {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS
  } catch {
    return DEFAULTS
  }
}

export function applyA11y(s: A11ySettings): void {
  const root = document.documentElement
  root.classList.toggle('a11y-large', s.largeText)
  root.classList.toggle('a11y-contrast', s.highContrast)
}

export function useA11y(): [A11ySettings, (patch: Partial<A11ySettings>) => void] {
  const [settings, setSettings] = useState<A11ySettings>(() => (typeof window === 'undefined' ? DEFAULTS : loadA11y()))
  useEffect(() => {
    applyA11y(settings)
    try { localStorage.setItem(KEY, JSON.stringify(settings)) } catch { /* 저장 불가 */ }
  }, [settings])
  const update = useCallback((patch: Partial<A11ySettings>) => setSettings((s) => ({ ...s, ...patch })), [])
  return [settings, update]
}

// ---------------------------------------------------------------- 음성 (Web Speech API)
export function speechSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined'
}

export function speak(text: string, opts: { rate?: number; interrupt?: boolean } = {}): boolean {
  if (!speechSupported() || !text.trim()) return false
  const synth = window.speechSynthesis
  if (opts.interrupt !== false) synth.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'ko-KR'
  u.rate = opts.rate ?? 0.95
  const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith('ko'))
  if (voice) u.voice = voice
  synth.speak(u)
  return true
}

export function stopSpeaking(): void {
  if (speechSupported()) window.speechSynthesis.cancel()
}

/** 구간 하나를 사람 말로. 시각장애인 안내에 맞춰 시설·주의를 먼저 말한다. */
export function legSentence(leg: Leg, index: number): string {
  const n = `${index + 1}번째`
  if (leg.kind === 'walk') {
    const parts = [`${n}, 도보 ${formatMinutes(leg.duration_s)}, ${formatDistance(leg.distance_m)}`]
    if (leg.stairs_count > 0) parts.push(`계단 ${leg.stairs_count}곳 있음`)
    if (leg.max_grade_pct !== null && leg.max_grade_pct >= 6) parts.push(`경사 ${leg.max_grade_pct.toFixed(0)}퍼센트 주의`)
    if (leg.crossings > 0) parts.push(`횡단보도 ${leg.crossings}번`)
    return parts.join(', ')
  }
  if (leg.kind === 'vertical') {
    const where = leg.station_name ? `${leg.station_name}에서 ` : ''
    const warn = leg.verified === null ? ', 엘리베이터 위치는 현장에서 확인하세요' : ''
    return `${n}, ${where}${legTitle(leg)} 이용${warn}`
  }
  const wait = leg.wait_s > 0 ? `, 대기 약 ${formatMinutes(leg.wait_s)}` : ''
  const low = leg.mode === 'bus' && leg.low_floor_ratio !== null ? `, 저상버스 비율 ${Math.round(leg.low_floor_ratio * 100)}퍼센트` : ''
  return `${n}, ${leg.from_name}에서 ${legTitle(leg)} 탑승, ${leg.stop_count}정거장 ${formatMinutes(leg.duration_s)}, ${leg.to_name}에서 하차${wait}${low}`
}

export function routeSpeech(route: Route, originName: string, destinationName: string): string {
  const head = `${originName || '출발지'}에서 ${destinationName || '도착지'}까지, 총 ${Math.round(route.total_duration_min)}분, 도보 ${formatDistance(route.walk_distance_m)}.`
  const cautions = route.cautions.length ? ` 주의: ${route.cautions.join('. ')}.` : ''
  const steps = route.legs.map((l, i) => legSentence(l, i)).join('. ')
  return `${head}${cautions} ${steps}. 도착입니다.`
}

export function resultsSpeech(count: number, best: Route | null): string {
  if (!best) return '경로를 찾지 못했어요.'
  return `경로 ${count}개를 찾았어요. 추천 경로는 ${Math.round(best.total_duration_min)}분, 도보 ${formatDistance(best.walk_distance_m)}입니다.`
}
