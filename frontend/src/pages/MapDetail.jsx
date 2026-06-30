import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { RadialBarChart, RadialBar, PolarAngleAxis, BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell, LabelList } from 'recharts'
import { UploadCloud, Network, X, AlertTriangle } from 'lucide-react'
import Badge from '../components/Badge'
import { fetchMaps, fetchMapDetail, fetchAssignments, fetchGraphImpact } from '../lib/api'
import { formatINR, daysRemaining, truncate } from '../lib/format'

const DEMO_MAPS = [
  { id: 'MAP001', map_id: 'MAP001', priority_tier: 'CRITICAL', penalty_exposure: 5000000, authority: 'RBI', status: 'OPEN', obligation_text: 'Banks must complete KYC re-verification for all high-risk customers.', mpi_score: 92, deadline: '2026-08-15', regulatory_reference: 'RBI/2026/KYC-01', map_type: 'MANDATORY', measurable_condition: 'Evidence must show completion of KYC re-verification for all flagged high-risk accounts.', evidence_required: 'Signed compliance attestation and customer re-verification log export.', wing_responsible: 'Retail Banking', mandate_id: 'MND001' },
  { id: 'MAP002', map_id: 'MAP002', priority_tier: 'HIGH', penalty_exposure: 3000000, authority: 'SEBI', status: 'IN_PROGRESS', obligation_text: 'Quarterly grievance redressal report implementation', mpi_score: 75, deadline: '2026-07-01', regulatory_reference: 'SEBI/2026/GR-04', map_type: 'MANDATORY', wing_responsible: 'Operations Wing', mandate_id: 'MND002' },
  { id: 'MAP003', map_id: 'MAP003', priority_tier: 'MEDIUM', penalty_exposure: 1500000, authority: 'IRDAI', status: 'OPEN', obligation_text: 'Cybersecurity audit compliance framework integration', mpi_score: 55, deadline: '2026-09-30', regulatory_reference: 'IRDAI/2026/CS-02', map_type: 'ADVISORY', wing_responsible: 'IT Security Wing', mandate_id: 'MND003' },
]

const DEMO_ASSIGNMENTS = [
  { wing: 'Retail Banking', role: 'Primary Executor', assignment_text: 'Execute customer re-verification based on updated guidelines.' },
  { wing: 'Compliance Wing', role: 'Monitor', assignment_text: 'Validate submitted evidence for completeness.' },
  { wing: 'Internal Audit', role: 'Final Review', assignment_text: 'Log cryptographic certificate and sign off.' },
]

function mpiTier(score) {
  if (score >= 80) return { color: '#f43f5e', label: 'CRITICAL' }
  if (score >= 60) return { color: '#f97316', label: 'HIGH' }
  if (score >= 40) return { color: '#eab308', label: 'MEDIUM' }
  return { color: '#00FF88', label: 'LOW' }
}

function Field({ label, value, color, full }) {
  return (
    <div className={`bg-[#0A0A0A] rounded-[24px] p-4 ${full ? 'col-span-3' : ''}`}>
      <p className="text-sm font-medium text-[#8B8B93] mb-2 font-sans">{label}</p>
      <p className="text-sm font-sans" style={{ color: color || '#FFFFFF' }}>{value || '—'}</p>
    </div>
  )
}

export default function MapDetail() {
  const { mapId } = useParams()
  const navigate = useNavigate()
  const [mapsList, setMapsList] = useState([])

  const groupedMaps = useMemo(() => {
  const groups = {}
  mapsList.forEach((mp) => {
    const key = mp.mandate_title || 'Unclassified Circular'
    if (!groups[key]) groups[key] = []
    groups[key].push(mp)
  })
  return groups
}, [mapsList])

  const [detail, setDetail] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [impact, setImpact] = useState(null)
  const [showImpact, setShowImpact] = useState(false)

  useEffect(() => {
    async function loadMaps() {
      try {
        const data = await fetchMaps()
        setMapsList(Array.isArray(data) ? data : [])
      } catch (e) {
        setError('Backend unreachable. Running in offline demo mode.')
        setMapsList(DEMO_MAPS)
      }
    }
    loadMaps()
  }, [])

  const resolvedId = useMemo(() => {
    if (mapId && mapId !== 'latest') return mapId
    if (mapsList.length > 0) return mapsList[0].id || mapsList[0].map_id
    return null
  }, [mapId, mapsList])

  useEffect(() => {
    if (!resolvedId) {
      setLoading(false)
      return
    }
    async function loadDetail() {
      setLoading(true)
      setError(null)
      try {
        const [detailData, assignData] = await Promise.all([
          fetchMapDetail(resolvedId),
          fetchAssignments(resolvedId),
        ])
        setDetail(detailData)
        setAssignments(Array.isArray(assignData) ? assignData : [])
      } catch (e) {
        setError('Backend unreachable. Running in offline demo mode.')
        const fallback = mapsList.find((m) => (m.id || m.map_id) === resolvedId)
          || DEMO_MAPS.find((m) => (m.id || m.map_id) === resolvedId)
          || DEMO_MAPS[0]
        setDetail(fallback)
        setAssignments(DEMO_ASSIGNMENTS)
      } finally {
        setLoading(false)
      }
    }
    loadDetail()
  }, [resolvedId, mapsList])

  if (!loading && mapsList.length === 0) {
    return (
      <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
        <div className="mb-8 pl-2">
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">MAP Detail</h1>
          <p className="text-[#8B8B93] text-sm">Mandatory action point · full view</p>
        </div>
        <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center py-16">
          <p className="text-white font-medium mb-2">No MAPs available</p>
          <p className="text-[#8B8B93] text-sm">Go to Mandates page and load demo data first</p>
        </div>
      </div>
    )
  }

  const m = detail || {}
  const mpi = Number(m.mpi_score || 0)
  const tier = m.priority_tier || 'LOW'
  const exposure = m.penalty_exposure || 0
  const deadline = m.deadline
  const dRemain = daysRemaining(deadline)
  const { color: mpiColor, label: mpiLabel } = mpiTier(mpi)

  const gaugeData = [{ name: 'mpi', value: mpi, fill: mpiColor }]

  const breakdownSource =
    m.mpi_breakdown && typeof m.mpi_breakdown === 'object'
      ? Object.entries(m.mpi_breakdown).map(([k, v]) => ({ name: k, value: Number(v) }))
      : [
          { name: 'Penalty × Likelihood', value: mpi * 0.49 },
          { name: 'Deadline Urgency', value: mpi * 0.22 },
          { name: 'Authority Weight', value: mpi * 0.11 },
          { name: 'Recurrence Risk', value: mpi * 0.18 },
        ]
  const breakdownColors = ['#00C6FF', '#7000FF', '#00FF88', '#8B8B93']

  const lodMeta = [
    { label: '1st Line of Defence · Business Wing', color: '#00C6FF' },
    { label: '2nd Line of Defence · Control Wing', color: '#7000FF' },
    { label: '3rd Line of Defence · Audit Wing', color: '#00FF88' },
  ]

  async function loadImpact() {
  const mandateId = m.mandate_id || m.mandate?.id
  if (!mandateId) return
  setShowImpact(true)
  try {
    const data = await fetchGraphImpact(mandateId)
    setImpact(data)
  } catch (e) {
    setImpact({ error: e.message })
  }
}

  return (
    <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
      <div className="mb-8 pl-2">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">MAP Detail</h1>
        <p className="text-[#8B8B93] text-sm">Mandatory action point · full view</p>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 px-5 py-4 rounded-[16px] bg-[#1A1100]">
          <AlertTriangle size={18} className="text-[#FFA500]" />
          <span className="text-[#FFA500] text-sm font-medium">{error}</span>
        </div>
      )}

      <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-6">
        <p className="text-sm font-medium text-[#8B8B93] mb-3">Select MAP</p>
        <select
  value={resolvedId || ''}
  onChange={(e) => navigate(`/map/${e.target.value}`)}
  className="w-full px-4 py-2.5 rounded-[12px] text-sm font-sans bg-[#1A1A1A] text-white outline-none"
>
  {Object.entries(groupedMaps).map(([title, maps]) => (
    <optgroup key={title} label={title.slice(0, 70)}>
      {maps.map((mp) => (
        <option key={mp.id || mp.map_id} value={mp.id || mp.map_id}>
          {(mp.obligation_text || '').slice(0, 55)}...
        </option>
      ))}
    </optgroup>
  ))}
</select>
      </div>

      {loading ? (
        <div className="space-y-4">
          <div className="h-40 bg-[#0A0A0A] rounded-[24px] animate-pulse" />
          <div className="h-24 bg-[#0A0A0A] rounded-[24px] animate-pulse" />
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-6">
          <div className="col-span-3 space-y-6">
            <div>
              <p className="text-sm font-medium text-[#8B8B93] mb-3">Obligation</p>
              <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-sm text-white leading-relaxed font-sans border-l-2 border-[#00C6FF]">
                {m.mandate_title && (
                  <p className="text-xs text-[#8B8B93] mb-2 font-sans">
                    From circular: <span className="text-[#00C6FF]">{m.mandate_title}</span>
                  </p>
                )}
                
                {m.obligation_text || '—'}
              </div>
            </div>

            {m.measurable_condition && (
              <div>
                <p className="text-sm font-medium text-[#8B8B93] mb-3">Measurable condition</p>
                <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-sm text-[#8B8B93] leading-relaxed font-sans border-l-2 border-[#7000FF]">
                  {m.measurable_condition}
                </div>
              </div>
            )}

            <div>
              <p className="text-sm font-medium text-[#8B8B93] mb-3">Details</p>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <Field label="Reference" value={m.regulatory_reference} />
                <Field label="MAP Type" value={m.map_type} />
                <Field label="Authority" value={m.authority || m.source} />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Deadline" value={deadline || '—'} />
                <Field
                  label="Days Remaining"
                  value={dRemain !== null ? `${dRemain}d` : '—'}
                  color={dRemain !== null && dRemain <= 7 ? '#FFA500' : undefined}
                />
                <Field label="Status" value={m.status || '—'} />
              </div>
            </div>

            {m.evidence_required && (
              <div>
                <p className="text-sm font-medium text-[#8B8B93] mb-3">Evidence required</p>
                <Field label="What to submit" value={m.evidence_required} full />
              </div>
            )}
          </div>

          <div className="col-span-2 space-y-4">
            <div>
              <p className="text-sm font-medium text-[#8B8B93] mb-3">Priority index</p>
              <div className="bg-[#0A0A0A] rounded-[24px] p-6">
                <ResponsiveContainer width="100%" height={200}>
                  <RadialBarChart innerRadius="70%" outerRadius="100%" data={gaugeData} startAngle={180} endAngle={0}>
                    <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
                    <RadialBar background={{ fill: '#1A1A1A' }} dataKey="value" cornerRadius={8} fill={mpiColor} />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="text-center -mt-16 mb-2">
                  <div className="text-4xl font-bold font-sans" style={{ color: mpiColor }}>{mpi}</div>
                  <div className="text-sm text-[#8B8B93] font-sans">MPI · {mpiLabel}</div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center">
                <p className="text-sm font-medium text-[#8B8B93] mb-2">Penalty exposure</p>
                <p className="text-xl font-bold text-white font-sans">{formatINR(exposure)}</p>
              </div>
              <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center">
                <p className="text-sm font-medium text-[#8B8B93] mb-2">Priority</p>
                <div className="mt-1 flex justify-center">
                  <Badge tier={tier} />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <button
                onClick={() => navigate('/evidence', { state: { mapId: resolvedId } })}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-full text-sm font-semibold text-white bg-gradient-to-r from-[#00C6FF] to-[#7000FF] hover:opacity-90 transition-opacity"
              >
                <UploadCloud size={14} />
                Upload Evidence
              </button>
              {(m.mandate_id || m.mandate?.id) && (
                <button
                  onClick={loadImpact}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-full text-sm font-semibold text-white bg-[#1A1A1A] hover:bg-[#2A2A2A] transition-colors"
                >
                  <Network size={14} className="text-[#00C6FF]" />
                  View Regulatory Impact
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {!loading && (
        <>
          <p className="text-sm font-medium text-[#8B8B93] mb-4 mt-8">Canara Bank wing assignments — three lines of defence</p>
          <div className="grid grid-cols-3 gap-4 mb-8">
            {assignments.length > 0
              ? assignments.slice(0, 3).map((a, i) => (
                  <div key={i} className="bg-[#0A0A0A] rounded-[24px] p-6">
                    <p className="text-sm font-medium text-[#8B8B93] mb-3">{lodMeta[i]?.label || `Line ${i + 1}`}</p>
                    <p className="text-white font-semibold text-sm mb-1 font-sans">{a.wing || '—'}</p>
                    <p className="text-sm text-[#8B8B93] mb-3 font-sans">{a.role}</p>
                    <p className="text-sm text-[#8B8B93] leading-relaxed font-sans whitespace-pre-line">{a.assignment_text}</p>
                  </div>
                ))
              : [
                  { label: lodMeta[0].label, wing: m.wing_responsible || m.wing || '—', text: `Action required — ${truncate(m.obligation_text, 80)}` },
                  { label: lodMeta[1].label, wing: 'Compliance Wing', text: `Monitor MAP. MPI Score: ${mpi} (${mpiLabel}). Exposure: ${formatINR(exposure)}.` },
                  { label: lodMeta[2].label, wing: 'Internal Audit Wing', text: 'Audit queue entry. Schedule evidence verification post-completion.' },
                ].map((card, i) => (
                  <div key={i} className="bg-[#0A0A0A] rounded-[24px] p-6">
                    <p className="text-sm font-medium text-[#8B8B93] mb-3">{card.label}</p>
                    <p className="text-white font-semibold text-sm mb-3 font-sans">{card.wing}</p>
                    <p className="text-sm text-[#8B8B93] leading-relaxed font-sans">{card.text}</p>
                  </div>
                ))}
          </div>

          <p className="text-sm font-medium text-[#8B8B93] mb-4">MPI score breakdown</p>
          <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-6">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={breakdownSource} barCategoryGap="40%">
                <CartesianGrid stroke="#1A1A1A" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#8B8B93', fontFamily: 'Inter, sans-serif', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#8B8B93', fontFamily: 'Inter, sans-serif', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {breakdownSource.map((_, i) => (
                    <Cell key={i} fill={breakdownColors[i % breakdownColors.length]} fillOpacity={0.85} />
                  ))}
                  <LabelList dataKey="value" position="top" formatter={(v) => v.toFixed(1)} fill="#FFFFFF" fontFamily="Inter, sans-serif" fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {showImpact && (
            <>
              <p className="text-sm font-medium text-[#8B8B93] mb-4">Regulatory impact — affected MAPs</p>
              <div className="space-y-3 mb-4">
                {impact?.error && (
                  <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-sm text-[#8B8B93] font-sans">
                    Knowledge graph: {impact.error}
                  </div>
                )}
                {impact && !impact.error && impact.length === 0 && (
                  <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-sm text-[#8B8B93] font-sans">
                    No related MAPs found.
                  </div>
                )}
                {Array.isArray(impact) &&
                  impact.map((im, i) => (
                    <div key={i} className="bg-[#0A0A0A] rounded-[24px] p-6">
                      <div className="text-sm text-[#8B8B93] font-sans">
                        {im.id || im.map_id} · {im.regulatory_reference}
                      </div>
                      <div className="text-sm text-white mt-2 font-sans">{truncate(im.obligation_text, 100)}</div>
                    </div>
                  ))}
              </div>
              <button
                onClick={() => setShowImpact(false)}
                className="flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white bg-[#1A1A1A] hover:bg-[#2A2A2A] transition-colors"
              >
                <X size={12} className="text-[#00C6FF]" />
                Close
              </button>
            </>
          )}
        </>
      )}
    </div>
  )
}
