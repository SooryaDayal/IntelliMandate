import { useEffect, useRef, useState } from 'react'
import { RotateCw, FolderOpen, RefreshCw, Activity, CheckCircle, AlertTriangle } from 'lucide-react'
import { fetchHistory, fetchScrapeStatus, triggerOnlineScrape, triggerOfflineLoad, triggerOrchestrate } from '../lib/api'

const DEMO_DATA = [
  { id: 'MND001', title: 'Guidelines on KYC Re-verification', date_issued: '2026-06-10', source: 'RBI', signal_type: 'MANDATORY_IMMEDIATE', maps_extracted: 2, processed: true },
  { id: 'MND002', title: 'Cybersecurity Framework Amendments', date_issued: '2026-06-18', source: 'SEBI', signal_type: 'MANDATORY_FUTURE', maps_extracted: 1, processed: false },
]

export default function Mandates() {
  const [mandates, setMandates] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState(null)
  const [polling, setPolling] = useState(false)
  const [scrapeStatus, setScrapeStatus] = useState(null)
  const pollRef = useRef(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchHistory()
      setMandates(Array.isArray(data) ? data : [])
    } catch (e) {
      setError('Backend unreachable. Running in offline demo mode.')
      setMandates(DEMO_DATA)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(); return () => clearInterval(pollRef.current) }, [])

  function startPolling() {
    setPolling(true)
    let count = 0
    pollRef.current = setInterval(async () => {
      count += 1
      try {
        const status = await fetchScrapeStatus()
        setScrapeStatus(status)
        if (['COMPLETE', 'DONE'].includes(status?.status?.toUpperCase()) || count >= 15) {
          clearInterval(pollRef.current); setPolling(false); load()
        }
      } catch {
        if (count >= 15) { clearInterval(pollRef.current); setPolling(false) }
      }
    }, 4000)
  }

  async function handleOnlineScrape() {
    try {
      setNotice({ type: 'info', text: 'Initiating global web scrape. Establishing secure connection...' })
      await triggerOnlineScrape(10)
      startPolling()
    } catch (e) { setNotice({ type: 'error', text: `Scrape failed — ${e.message}` }) }
  }

  async function handleDemoLoad() {
    try {
      setNotice({ type: 'success', text: 'Offline cache injection initiated. Loading secure payloads...' })
      await triggerOfflineLoad()
      startPolling()
    } catch (e) { setNotice({ type: 'error', text: `Demo load failed — ${e.message}` }) }
  }

  async function handleProcess(mandateId) {
    try {
      setNotice({ type: 'info', text: `Executing ReAct Orchestrator for ${mandateId}...` })
      await triggerOrchestrate(mandateId)
      setTimeout(load, 2000)
    } catch (e) { setNotice({ type: 'error', text: `Orchestration Failed — ${e.message}` }) }
  }

  const noticeColors = {
    info: { bg: '#00112A', text: '#00C6FF' },
    success: { bg: '#001A11', text: '#00FF88' },
    error: { bg: '#1A1100', text: '#FFA500' },
  }

  if (loading) return (
    <div className="fade-in p-10 max-w-[1400px] mx-auto font-sans">
      <div className="h-[200px] bg-[#0A0A0A] rounded-[24px] animate-pulse mb-6" />
      <div className="space-y-4">{[1, 2, 3].map(i => <div key={i} className="h-24 bg-[#0A0A0A] rounded-[24px] animate-pulse" />)}</div>
    </div>
  )

  return (
    <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
      <div className="mb-8 pl-2">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Mandate Pipeline</h1>
        <p className="text-[#8B8B93] text-sm">Regulatory ingestion and NLP processing engine</p>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 px-5 py-4 rounded-[16px] bg-[#1A1100]">
          <AlertTriangle size={18} className="text-[#FFA500]" />
          <span className="text-[#FFA500] text-sm font-medium">{error}</span>
        </div>
      )}

      <div className="flex gap-4 mb-6">
        <button onClick={handleOnlineScrape} className="flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white transition-all bg-gradient-to-r from-[#00C6FF] to-[#7000FF] hover:opacity-90">
          <RotateCw size={16} /> Run Live Web Scrape
        </button>
        <button onClick={handleDemoLoad} className="flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white bg-[#1A1A1A] hover:bg-[#2A2A2A] transition-all">
          <FolderOpen size={16} /> Load Local Cache
        </button>
      </div>

      {notice && (
        <div className="mb-6 px-5 py-4 rounded-[16px] text-sm font-medium" style={{ backgroundColor: noticeColors[notice.type].bg, color: noticeColors[notice.type].text }}>
          {notice.text}
        </div>
      )}

      {polling && (
        <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-8">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-white font-semibold flex items-center gap-2"><Activity size={18} className="text-[#00C6FF] animate-pulse" /> Live Telemetry</h3>
            <span className="text-[#00C6FF] text-sm font-medium">Processing...</span>
          </div>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <p className="text-sm font-medium text-[#8B8B93] mb-1">Documents Found</p>
              <p className="text-white text-4xl font-bold">{scrapeStatus?.circulars_found ?? '—'}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-[#8B8B93] mb-1">Successfully Stored</p>
              <p className="text-[#00FF88] text-4xl font-bold">{scrapeStatus?.circulars_stored ?? '—'}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-[#8B8B93] mb-1">Duplicates Skipped</p>
              <p className="text-[#8B8B93] text-4xl font-bold">{scrapeStatus?.circulars_skipped ?? '—'}</p>
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-between items-end mb-4 pl-2">
        <p className="text-sm font-medium text-[#8B8B93]">Ingestion History</p>
        <button onClick={load} className="text-[#8B8B93] hover:text-[#00C6FF] transition-colors flex items-center gap-1 text-sm font-medium">
          <RefreshCw size={14} className="text-[#00C6FF]" /> Refresh
        </button>
      </div>

      <div className="space-y-4">
        {mandates.map((m) => {
          const mId = m.id || m.mandate_id
          const processed = !!m.processed
          return (
            <div key={mId} className="bg-[#0A0A0A] rounded-[24px] p-6 flex items-center justify-between transition-colors hover:bg-[#111111]">
              <div className="flex-1 min-w-0 pr-6">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-sm text-[#8B8B93]">{mId}</span>
                  <span className="px-2.5 py-1 rounded-[6px] text-xs font-semibold bg-[#1A1A1A] text-white">{m.source}</span>
                  {processed ? (
                    <span className="text-[#00FF88] flex items-center gap-1.5 text-sm font-medium"><CheckCircle size={14} /> Indexed</span>
                  ) : (
                    <span className="text-[#FFA500] flex items-center gap-1.5 text-sm font-medium"><Activity size={14} /> Pending Extraction</span>
                  )}
                </div>
                <h4 className="text-white font-medium text-lg mb-2 leading-snug">{m.title || 'Untitled Circular'}</h4>
                <div className="flex gap-4 text-sm text-[#8B8B93]">
                  <span className="text-[#00C6FF]">◆ {m.signal_type}</span>
                  <span>Issued: {(m.date_issued || m.created_at || '—').slice(0, 10)}</span>
                </div>
              </div>
              <div className="flex items-center gap-8 shrink-0">
                <div className="text-right">
                  <p className="text-sm font-medium text-[#8B8B93] mb-1">MAPs Extracted</p>
                  <p className="text-white text-3xl font-bold">{m.maps_extracted ?? m.map_count ?? 0}</p>
                </div>
                {!processed && (
                  <button onClick={() => handleProcess(mId)} className="h-10 px-5 rounded-full text-sm font-semibold text-white bg-gradient-to-r from-[#00C6FF] to-[#7000FF] hover:opacity-90 transition-opacity">
                    Process Now
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
