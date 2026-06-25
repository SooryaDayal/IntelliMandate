import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Upload, AlertTriangle } from 'lucide-react'
import Badge from '../components/Badge'
import { fetchMaps, fetchMapDetail, uploadEvidence, validateEvidence, sha256Hex } from '../lib/api'
import { tierClass } from '../lib/format'

const DEMO_DATA = [
  { id: 'MAP001', map_id: 'MAP001', priority_tier: 'CRITICAL', status: 'OPEN', regulatory_reference: 'RBI/2026/KYC-01', obligation_text: 'Banks must complete KYC re-verification for all high-risk customers.', wing_responsible: 'Retail Banking', deadline: '2026-08-15', measurable_condition: 'Evidence must show completion of KYC re-verification for all flagged high-risk accounts.', evidence_required: 'Signed compliance attestation and customer re-verification log export.' },
  { id: 'MAP002', map_id: 'MAP002', priority_tier: 'HIGH', status: 'IN_PROGRESS', regulatory_reference: 'SEBI/2026/GR-04', obligation_text: 'Quarterly grievance redressal report implementation', wing_responsible: 'Operations Wing', deadline: '2026-07-01', measurable_condition: 'Report must cover all grievances received in the quarter with resolution timelines.', evidence_required: 'Quarterly grievance redressal report PDF with management sign-off.' },
  { id: 'MAP003', map_id: 'MAP003', priority_tier: 'MEDIUM', status: 'OPEN', regulatory_reference: 'IRDAI/2026/CS-02', obligation_text: 'Cybersecurity audit compliance framework integration', wing_responsible: 'IT Security Wing', deadline: '2026-09-30', measurable_condition: 'Evidence must demonstrate completion of third-party cybersecurity audit.', evidence_required: 'Audit report and remediation tracker.' },
]

const GATE_DEFS = [
  { key: 'gate_1_deadline', no: 1, name: 'Deadline Check' },
  { key: 'gate_2_integrity', no: 2, name: 'Integrity Hash' },
  { key: 'gate_3_temporal', no: 3, name: 'Temporal Check' },
  { key: 'gate_4_semantic', no: 4, name: 'Semantic Match' },
]

function GateRow({ no, name, status, reason }) {
  const statusStyles = {
    PASSED: { icon: '✓', color: 'text-[#00FF88]' },
    REVIEW: { icon: '⚠', color: 'text-[#FFA500]' },
    FAILED: { icon: '✕', color: 'text-[#FFA500]' },
  }
  const { icon, color } = statusStyles[status] || { icon: '⟳', color: 'text-[#8B8B93]' }
  return (
    <div className="flex items-center gap-4 px-5 py-3.5 rounded-[16px] mb-2 bg-[#0A0A0A]">
      <span className="text-sm text-[#8B8B93] w-12 font-sans">Gate {no}</span>
      <div className="flex-1">
        <div className={`text-sm font-sans ${status ? 'text-white' : 'text-[#8B8B93]'}`}>{name}</div>
        {reason && <div className="text-sm text-[#8B8B93] mt-1 font-sans">{reason}</div>}
      </div>
      <span className={`text-sm font-semibold font-sans ${color}`}>
        {icon} {status || 'WAITING'}
      </span>
    </div>
  )
}

export default function EvidenceUpload() {
  const location = useLocation()
  const fileRef = useRef(null)
  const [mapsList, setMapsList] = useState([])
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(location.state?.mapId || null)
  const [detail, setDetail] = useState(null)
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [gateResults, setGateResults] = useState({})
  const [finalCert, setFinalCert] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [stillProcessing, setStillProcessing] = useState(false)

  useEffect(() => {
    async function loadMaps() {
      try {
        const all = await fetchMaps()
        const open = (Array.isArray(all) ? all : []).filter((m) => (m.status || '').toUpperCase() !== 'CLOSED')
        setMapsList(open)
        if (!selectedId && open.length > 0) {
          setSelectedId(open[0].id || open[0].map_id)
        }
      } catch (e) {
        setError('Backend unreachable. Running in offline demo mode.')
        const open = DEMO_DATA.filter((m) => (m.status || '').toUpperCase() !== 'CLOSED')
        setMapsList(open)
        if (!selectedId && open.length > 0) {
          setSelectedId(open[0].id || open[0].map_id)
        }
      }
    }
    loadMaps()
  }, [])

  useEffect(() => {
    if (!selectedId) return
    async function loadDetail() {
      try {
        const data = await fetchMapDetail(selectedId)
        setDetail(data)
      } catch {
        const fallback = mapsList.find((m) => (m.id || m.map_id) === selectedId)
          || DEMO_DATA.find((m) => (m.id || m.map_id) === selectedId)
        setDetail(fallback || null)
      }
    }
    loadDetail()
  }, [selectedId, mapsList])

  const openIds = mapsList.map((m) => m.id || m.map_id).filter(Boolean)

  if (openIds.length === 0 && mapsList.length === 0 && !error) {
    return (
      <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
        <div className="mb-8 pl-2">
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Evidence Upload</h1>
          <p className="text-[#8B8B93] text-sm">Submit compliance evidence · gate validation</p>
        </div>
        <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center py-16">
          <Upload size={32} className="mx-auto mb-4 text-[#00C6FF]" />
          <p className="text-white font-medium mb-2">No open MAPs to submit evidence for</p>
          <p className="text-[#8B8B93] text-sm">All MAPs are closed, or none have been created yet</p>
        </div>
      </div>
    )
  }

  async function handleSubmit() {
    if (!file || !selectedId) return
    setSubmitting(true)
    setSubmitError(null)
    setFinalCert(null)
    setStillProcessing(false)
    setGateResults({})

    const arrayBuffer = await file.arrayBuffer()
    const fileHash = await sha256Hex(arrayBuffer)

    setGateResults((g) => ({ ...g, gate_2_integrity: { status: 'PASSED', reason: `SHA-256: ${fileHash.slice(0, 24)}...` } }))

    let evidenceId
    try {
      const res = await uploadEvidence(selectedId, { file, fileHash })
      evidenceId = res.evidence_id || res.id
    } catch (e) {
      setSubmitError(e.message)
      setSubmitting(false)
      return
    }

    if (!evidenceId) {
      setSubmitting(false)
      setStillProcessing(true)
      return
    }

    let final = null
    for (let i = 0; i < 15; i++) {
      let vdata
      try {
        vdata = await validateEvidence(evidenceId)
      } catch {
        await new Promise((r) => setTimeout(r, 3000))
        continue
      }

      const gr = vdata.gate_results || {}
      setGateResults((g) => ({ ...g, ...gr, gate_2_integrity: gr.gate_2_integrity || g.gate_2_integrity }))

      const status = (vdata.status || vdata.map_status || '').toUpperCase()
      const allFourPresent = GATE_DEFS.every((gd) => gr[gd.key])
      if (allFourPresent || ['CLOSED', 'REVIEW', 'FAILED', 'RESUBMIT'].includes(status)) {
        final = vdata
        break
      }
      await new Promise((r) => setTimeout(r, 3000))
    }

    setSubmitting(false)
    if (final) {
      setFinalCert(final)
    } else {
      setStillProcessing(true)
    }
  }

  const wing = detail?.wing_responsible || detail?.wing || '—'
  const outcome = (finalCert?.status || finalCert?.map_status || '').toUpperCase()
  const g4 = finalCert?.gate_results?.gate_4_semantic || {}

  return (
    <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
      <div className="mb-8 pl-2">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Evidence Upload</h1>
        <p className="text-[#8B8B93] text-sm">Submit compliance evidence · gate validation</p>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 px-5 py-4 rounded-[16px] bg-[#1A1100]">
          <AlertTriangle size={18} className="text-[#FFA500]" />
          <span className="text-[#FFA500] text-sm font-medium">{error}</span>
        </div>
      )}

      {openIds.length > 0 && (
        <>
          <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-6">
            <p className="text-sm font-medium text-[#8B8B93] mb-3">Select MAP</p>
            <select
              value={selectedId || ''}
              onChange={(e) => setSelectedId(e.target.value)}
              className="w-full px-4 py-2.5 rounded-[12px] text-sm font-sans bg-[#1A1A1A] text-white outline-none"
            >
              {openIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>

          {detail && (
            <div className={`tier-card ${tierClass(detail.priority_tier)} bg-[#0A0A0A] rounded-[24px] p-6 flex items-center gap-5 mb-6`}>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-[#8B8B93] mb-2 font-sans">
                  {selectedId} · {detail.regulatory_reference || '—'}
                </div>
                <div className="text-white font-semibold text-base mb-3 font-sans">
                  {detail.obligation_text || '—'}
                </div>
                <div className="flex gap-4 text-sm text-[#8B8B93] font-sans">
                  <span>🏛 Wing: {wing}</span>
                  <span>⏱ Deadline: {detail.deadline || '—'}</span>
                </div>
              </div>
              <Badge tier={detail.priority_tier} />
            </div>
          )}

          {detail?.measurable_condition && (
            <div className="mb-6">
              <p className="text-sm font-medium text-[#8B8B93] mb-3">Measurable condition — what proof must show</p>
              <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-sm text-white leading-relaxed font-sans border-l-2 border-[#00C6FF]">
                {detail.measurable_condition}
              </div>
            </div>
          )}

          {detail?.evidence_required && (
            <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-6">
              <p className="text-sm font-medium text-[#8B8B93] mb-2">Evidence required</p>
              <p className="text-sm text-white font-sans">{detail.evidence_required}</p>
            </div>
          )}

          <p className="text-sm font-medium text-[#8B8B93] mb-3">Submit evidence</p>
          <div
            onClick={() => fileRef.current?.click()}
            className="cursor-pointer bg-[#0A0A0A] rounded-[24px] p-6 text-center mb-4 hover:bg-[#111111] transition-colors"
          >
            <Upload size={22} className="mx-auto mb-2 text-[#00C6FF]" />
            <div className="text-sm text-[#8B8B93] font-sans">
              {file ? file.name : 'Upload proof — PDF, DOCX, TXT, PNG, or JPG'}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={!file || submitting}
            className={`w-full px-4 py-3 rounded-full text-sm font-semibold mb-6 transition-opacity ${
              !file || submitting
                ? 'bg-[#1A1A1A] text-[#8B8B93] cursor-not-allowed'
                : 'bg-gradient-to-r from-[#00C6FF] to-[#7000FF] text-white hover:opacity-90'
            }`}
          >
            Submit Evidence
          </button>

          {submitError && (
            <div className="bg-[#1A1100] rounded-[16px] px-5 py-3 mb-4 text-sm text-[#FFA500] font-sans">
              ⚠ Evidence upload failed — {submitError}
            </div>
          )}

          {(submitting || Object.keys(gateResults).length > 0) && (
            <div className="mb-6">
              <p className="text-sm font-medium text-[#8B8B93] mb-3">Validation gates</p>
              {GATE_DEFS.map((gd) => {
                const g = gateResults[gd.key]
                return <GateRow key={gd.key} no={gd.no} name={gd.name} status={g?.status} reason={g?.reason} />
              })}
            </div>
          )}

          {finalCert && (
            <>
              {outcome === 'CLOSED' && (
                <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center mt-2">
                  <div className="text-2xl mb-2 text-[#00FF88]">✓</div>
                  <div className="font-bold text-[#00FF88] text-lg font-sans">
                    Canara Bank MAP closed
                  </div>
                  <div className="text-sm text-[#8B8B93] mt-2 font-sans">
                    Compliance obligation fulfilled. Certificate generated.
                  </div>
                </div>
              )}
              {outcome === 'REVIEW' && (
                <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center mt-2">
                  <div className="text-2xl mb-2 text-[#FFA500]">⚠</div>
                  <div className="font-bold text-[#FFA500] text-lg font-sans">
                    Compliance wing review required
                  </div>
                  <div className="text-sm text-[#8B8B93] mt-2 font-sans">
                    Semantic score {g4.score ?? '—'}. Manual review needed.
                    <br />
                    Wing: Compliance Wing to verify evidence.
                  </div>
                </div>
              )}
              {outcome !== 'CLOSED' && outcome !== 'REVIEW' && (
                <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center mt-2">
                  <div className="text-2xl mb-2 text-[#FFA500]">✕</div>
                  <div className="font-bold text-[#FFA500] text-lg font-sans">
                    Resubmission required
                  </div>
                  <div className="text-sm text-[#8B8B93] mt-2 font-sans">
                    Evidence does not prove: {detail?.measurable_condition || 'the required condition'}
                    <br />
                    Guidance: {g4.reason || 'Evidence does not address the compliance requirement.'}
                  </div>
                </div>
              )}
            </>
          )}

          {stillProcessing && !finalCert && (
            <div className="bg-[#0A0A0A] rounded-[24px] p-6 mt-2 text-sm text-[#8B8B93] font-sans">
              ⟳ Validation still in progress on the server. Refresh this page in a moment to see the final result.
            </div>
          )}
        </>
      )}
    </div>
  )
}
