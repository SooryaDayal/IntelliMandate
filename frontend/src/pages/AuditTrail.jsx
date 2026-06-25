import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react'
import { fetchAudit } from '../lib/api'
import { formatINR, truncate } from '../lib/format'

const DEMO_DATA = [
  {
    map_id: 'MAP004',
    regulatory_reference: 'FIU/2026/021',
    obligation_text: 'FEMA annual return filing for cross-border accounts',
    closed_at: '2026-06-20T14:22:00Z',
    semantic_score: 0.94,
    wing: 'Compliance Wing',
    wing_verified_by: 'Compliance Wing',
    evidence: { file_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
    gate_results: {
      gate_1_deadline: { status: 'PASSED', reason: 'Deadline met within tolerance window.' },
      gate_2_integrity: { status: 'PASSED', reason: 'SHA-256 hash verified against stored evidence.' },
      gate_3_temporal: { status: 'PASSED', reason: 'Evidence timestamp within valid submission range.' },
      gate_4_semantic: { status: 'PASSED', reason: 'Semantic score above closure threshold.' },
    },
  },
]

function gatePill(status) {
  const s = (status || '—').toUpperCase()
  const styles = {
    PASSED: 'bg-[#001A11] text-[#00FF88]',
    REVIEW: 'bg-[#1A1100] text-[#FFA500]',
    FAILED: 'bg-[#1A1100] text-[#FFA500]',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold font-sans ${styles[s] || 'bg-[#1A1A1A] text-[#8B8B93]'}`}>
      {s}
    </span>
  )
}

function CertRow({ k, v }) {
  return (
    <div className="flex justify-between py-2 border-b border-[#1A1A1A] last:border-0 text-sm font-sans">
      <span className="text-[#8B8B93]">{k}</span>
      <span className="text-white text-right max-w-[60%] break-all">{v}</span>
    </div>
  )
}

export default function AuditTrail() {
  const [records, setRecords] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAudit()
      setRecords(Array.isArray(data) ? data : [])
    } catch (e) {
      setError('Backend unreachable. Running in offline demo mode.')
      setRecords(DEMO_DATA)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const sorted = useMemo(
    () => [...records].sort((a, b) => (b.closed_at || b.created_at || '').localeCompare(a.closed_at || a.created_at || '')),
    [records]
  )

  const totalClosed = sorted.length
  const scores = sorted.map((r) => Number(r.semantic_score)).filter((s) => !isNaN(s))
  const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0
  const totalResolved = sorted.reduce((sum, r) => sum + Number(r.penalty_exposure || 0), 0)

  const wingCounts = {}
  sorted.forEach((r) => {
    const w = r.wing_verified_by || r.wing || '—'
    wingCounts[w] = (wingCounts[w] || 0) + 1
  })
  const topWing = Object.keys(wingCounts).length ? Object.entries(wingCounts).sort((a, b) => b[1] - a[1])[0][0] : '—'

  const metrics = [
    { label: 'Total Closed MAPs', value: totalClosed, color: '#00FF88' },
    { label: 'Avg Semantic Score', value: avgScore.toFixed(2), color: '#00C6FF' },
    { label: 'Exposure Resolved', value: formatINR(totalResolved), color: '#FFFFFF' },
    { label: 'Most Closures', value: topWing, color: '#FFFFFF', small: true },
  ]

  return (
    <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
      <div className="mb-8 pl-2">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Canara Bank Compliance Certificates</h1>
        <p className="text-[#8B8B93] text-sm">Cryptographically sealed audit records · closed MAPs</p>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 px-5 py-4 rounded-[16px] bg-[#1A1100]">
          <AlertTriangle size={18} className="text-[#FFA500]" />
          <span className="text-[#FFA500] text-sm font-medium">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-6">
        {metrics.map((m) => (
          <div key={m.label} className="bg-[#0A0A0A] rounded-[24px] p-6">
            <p className="text-sm font-medium text-[#8B8B93] mb-2">{m.label}</p>
            <p className={`font-bold tracking-tight ${m.small ? 'text-lg' : 'text-3xl'}`} style={{ color: m.color }}>
              {m.value}
            </p>
          </div>
        ))}
      </div>

      <p className="text-sm font-medium text-[#8B8B93] mb-4 pl-2">Closed MAPs</p>

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-[#0A0A0A] rounded-[24px] animate-pulse" />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center py-16">
          <CheckCircle size={32} className="mx-auto mb-4 text-[#00C6FF]" />
          <p className="text-white font-medium mb-2">No closed MAPs yet</p>
          <p className="text-[#8B8B93] text-sm">Closed MAPs and their certificates will appear here once evidence is validated</p>
        </div>
      ) : (
        <div className="space-y-4">
          {sorted.map((r, idx) => {
            const mapId = r.map_id || '—'
            const wing = r.wing_verified_by || r.wing || '—'
            const closedAt = (r.closed_at || '—').slice(0, 19).replace('T', ' ')
            const score = r.semantic_score
            const gr = r.gate_results || {}
            const isOpen = !!expanded[idx]

            return (
              <div key={idx}>
                <div className="bg-[#0A0A0A] rounded-[24px] p-6 flex items-center gap-4">
                  <div className="flex items-center justify-center shrink-0 w-7 h-7 rounded-full bg-[#001A11] text-[#00FF88] text-sm">
                    ✓
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-semibold text-sm mb-1">
                      {truncate(r.obligation_text, 70)}
                    </div>
                    <div className="text-sm text-[#8B8B93]">
                      {mapId} · {r.regulatory_reference || '—'} · 🏛 {wing} · Closed {closedAt}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-medium text-[#8B8B93] mb-1">Semantic Score</p>
                    <p className="text-[#00FF88] font-bold text-lg">
                      {score !== undefined && score !== null ? Number(score).toFixed(2) : '—'}
                    </p>
                  </div>
                  <button
                    onClick={() => setExpanded((e) => ({ ...e, [idx]: !e[idx] }))}
                    className="shrink-0 px-2 py-1 text-[#8B8B93] hover:text-[#00C6FF] transition-colors"
                  >
                    <ChevronDown size={16} className={`text-[#00C6FF] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                  </button>
                </div>

                {isOpen && (
                  <div className="bg-[#0A0A0A] rounded-[24px] p-6 mt-2">
                    <div className="bg-[#0A0A0A] rounded-[16px] p-4">
                      <CertRow k="map_id" v={mapId} />
                      <CertRow k="regulation_reference" v={r.regulatory_reference || '—'} />
                      <CertRow k="closed_at" v={r.closed_at || '—'} />
                      <CertRow k="evidence_file_hash" v={<span className="text-[#00C6FF]">{r.evidence?.file_hash || r.file_hash || '—'}</span>} />
                      <CertRow k="semantic_score" v={<span className="text-[#00FF88]">{score ?? '—'}</span>} />
                      <CertRow k="gate_1_deadline" v={gatePill(gr.gate_1_deadline?.status)} />
                      <CertRow k="gate_2_integrity" v={gatePill(gr.gate_2_integrity?.status)} />
                      <CertRow k="gate_3_temporal" v={gatePill(gr.gate_3_temporal?.status)} />
                      <CertRow k="gate_4_semantic" v={gatePill(gr.gate_4_semantic?.status)} />
                      <CertRow k="wing_verified_by" v={wing} />
                      <CertRow k="validator" v={r.validator || 'IntelliMandate v1.0'} />
                      <CertRow k="bank" v="Canara Bank" />
                    </div>

                    {[
                      ['Gate 1 — Deadline', gr.gate_1_deadline],
                      ['Gate 2 — Integrity', gr.gate_2_integrity],
                      ['Gate 3 — Temporal', gr.gate_3_temporal],
                      ['Gate 4 — Semantic', gr.gate_4_semantic],
                    ].map(([gname, g]) =>
                      g?.reason ? (
                        <div key={gname} className="mt-3 pl-3 border-l-2 border-[#1A1A1A] text-sm text-[#8B8B93]">
                          <strong className="text-white">{gname}:</strong> {g.reason}
                        </div>
                      ) : null
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <button
        onClick={load}
        className="mt-6 flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white bg-gradient-to-r from-[#00C6FF] to-[#7000FF] hover:opacity-90 transition-opacity"
      >
        <RefreshCw size={14} />
        Refresh
      </button>
    </div>
  )
}
