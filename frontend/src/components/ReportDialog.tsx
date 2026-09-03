import { useEffect, useState } from 'react'
import { createReport, fetchReportKinds } from '../api'

export type ReportTarget = { lat: number; lng: number; placeName?: string; requestId?: string; defaultKind?: string }

const FALLBACK_KINDS = [
  { kind: 'elevator_broken', label: '엘리베이터 고장' }, { kind: 'stairs', label: '계단 있음' }, { kind: 'kerb', label: '턱 있음' },
  { kind: 'blocked', label: '통행 불가' }, { kind: 'ok', label: '문제 없음(정보 정정)' }, { kind: 'other', label: '기타' },
]

/** 시설 제보 대화상자. 제보는 관리자가 확인한 뒤 경로 계산에 반영된다. */
export default function ReportDialog({ target, onClose, onDone }: { target: ReportTarget; onClose: () => void; onDone: (msg: string) => void }) {
  const [kinds, setKinds] = useState(FALLBACK_KINDS)
  const [kind, setKind] = useState(target.defaultKind ?? 'elevator_broken')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { fetchReportKinds().then((k) => k.length && setKinds(k)).catch(() => undefined) }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await createReport({ lat: target.lat, lng: target.lng, kind, note, place_name: target.placeName ?? '', request_id: target.requestId })
      onDone('제보했어요. 확인 후 경로에 반영돼요')
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '제보하지 못했어요')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal" role="presentation" onClick={onClose}>
      <div className="modal__box" role="dialog" aria-modal="true" aria-labelledby="report-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="report-title" className="modal__title">시설 제보</h2>
        <p className="modal__sub">{target.placeName ? `${target.placeName} 근처` : '이 위치'}의 문제를 알려 주세요. 확인되면 다른 분들 경로에도 바로 반영돼요.</p>
        <div className="modal__kinds" role="radiogroup" aria-label="제보 종류">
          {kinds.map((k) => (
            <button key={k.kind} type="button" role="radio" aria-checked={kind === k.kind} className={`chip${kind === k.kind ? ' is-on' : ''}`} onClick={() => setKind(k.kind)}>{k.label}</button>
          ))}
        </div>
        <label className="modal__field">
          <span>메모 (선택)</span>
          <textarea value={note} onChange={(e) => setNote(e.target.value.slice(0, 500))} rows={3} placeholder="예: 1번 출구 엘리베이터가 오늘 점검 중이에요" />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="modal__actions">
          <button type="button" className="cta cta--ghost" onClick={onClose}>취소</button>
          <button type="button" className="cta" onClick={submit} disabled={busy}>{busy ? '보내는 중…' : '제보하기'}</button>
        </div>
      </div>
    </div>
  )
}
