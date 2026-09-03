import { useEffect, useRef, useState } from 'react'
import { speechSupported, type A11ySettings } from '../lib/a11y'

/** 접근성 메뉴: 큰 글씨, 고대비, 음성 안내. */
export default function A11yMenu({ settings, onChange }: { settings: A11ySettings; onChange: (patch: Partial<A11ySettings>) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  const on = settings.largeText || settings.highContrast || settings.voice
  return (
    <div className="a11y" ref={ref}>
      <button type="button" className={`a11y__btn${on ? ' is-on' : ''}`} onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="true" aria-label="접근성 설정">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="4.5" r="2" /><path d="M4 9h16M12 9v6M12 15l-4 6M12 15l4 6" /></svg>
      </button>
      {open && (
        <div className="a11y__menu" role="group" aria-label="접근성">
          <label className="a11y__row"><input type="checkbox" checked={settings.largeText} onChange={(e) => onChange({ largeText: e.target.checked })} /><span>큰 글씨</span></label>
          <label className="a11y__row"><input type="checkbox" checked={settings.highContrast} onChange={(e) => onChange({ highContrast: e.target.checked })} /><span>고대비</span></label>
          <label className="a11y__row"><input type="checkbox" checked={settings.voice} disabled={!speechSupported()} onChange={(e) => onChange({ voice: e.target.checked })} /><span>음성 안내{speechSupported() ? '' : ' (이 브라우저는 지원 안 함)'}</span></label>
          <p className="a11y__hint">화면 읽기 프로그램을 쓰시면 결과와 안내가 자동으로 읽혀요.</p>
        </div>
      )}
    </div>
  )
}
