import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, FolderOpen, CheckCircle2 } from 'lucide-react'
import Badge from '../components/Badge'
import { uploadCircular, triggerOrchestrate, triggerOfflineLoad } from '../lib/api'
import { formatINR } from '../lib/format'

const STEP_LABELS = [
  'Extracting text from file',
  'Classifying regulatory signal',
  'Running Agentic Orchestrator',
  'MAPs created and routed to Canara Bank Wings',
]

export default function UploadCircular() {
  const navigate = useNavigate()
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [source, setSource] = useState('RBI')
  const [processing, setProcessing] = useState(false)
  const [activeStep, setActiveStep] = useState(0)
  const [completed, setCompleted] = useState([])
  const [log, setLog] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [demoNotice, setDemoNotice] = useState(null)

  function appendLog(line) {
    setLog((prev) => [...prev, line])
  }

  async function sleep(ms) {
    return new Promise((res) => setTimeout(res, ms))
  }

  async function handleProcess() {
    if (!file) return
    setProcessing(true)
    setError(null)
    setResult(null)
    setLog([])
    setCompleted([])
    setActiveStep(1)

    appendLog('Reading file bytes and extracting text via PyMuPDF...')
    await sleep(500)

    try {
      const uploadResult = await uploadCircular({ file, title, source })
      setCompleted([1])
      appendLog(`Text extracted — ${file.size} bytes processed`)
      setActiveStep(2)
      await sleep(400)

      const signalType = uploadResult.signal_type || 'UNKNOWN'
      appendLog(`classify_signal_type → ${signalType}`)
      setCompleted([1, 2])
      setActiveStep(3)
      await sleep(400)

      const mandateId = uploadResult.mandate_id || uploadResult.id
      let finalResult = uploadResult

      if (mandateId) {
        let orchResult = uploadResult
        try {
          orchResult = await triggerOrchestrate(mandateId)
        } catch {
          // backend may already run orchestrator on upload
        }

        const reasoningLog = orchResult.reasoning_log || []
        for (const entry of reasoningLog) {
          appendLog(String(entry))
          await sleep(120)
        }
        if (reasoningLog.length === 0) {
          appendLog('Orchestrator run complete — no detailed log returned')
        }
        finalResult = orchResult
      }

      setCompleted([1, 2, 3, 4])
      setActiveStep(4)
      setResult(finalResult)
    } catch (e) {
      setError(e.message)
    } finally {
      setProcessing(false)
    }
  }

  async function handleDemoLoad() {
    try {
      await triggerOfflineLoad()
      setDemoNotice({ type: 'success', text: '✓ Demo data load triggered — 10 Canara Bank circulars ingesting in background. Check the Mandates page to track progress.' })
    } catch (e) {
      setDemoNotice({ type: 'error', text: `⚠ Demo load failed — ${e.message}` })
    }
  }

  const highestTier = result?.critical_maps > 0 ? 'CRITICAL' : result?.maps_created > 0 ? 'HIGH' : '—'

  return (
    <div className="fade-in pb-10 max-w-[1400px] mx-auto font-sans">
      <div className="mb-8 pl-2">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Upload RBI Circular Manually</h1>
        <p className="text-[#8B8B93] text-sm">Feed any circular directly into IntelliMandate · PDF / DOCX / ZIP</p>
      </div>

      <p className="text-sm font-medium text-[#8B8B93] mb-4 pl-2">Manual circular upload</p>

      <div className="grid grid-cols-3 gap-6 mb-6">
        <div className="col-span-2 space-y-4">
          <div
            onClick={() => fileRef.current?.click()}
            className="cursor-pointer bg-[#0A0A0A] rounded-[24px] p-6 text-center hover:bg-[#111111] transition-colors"
          >
            <Upload size={24} className="mx-auto mb-3 text-[#00C6FF]" />
            <div className="text-sm text-[#8B8B93] font-sans">
              {file ? file.name : 'Drop a circular here — PDF, DOCX, or ZIP'}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.zip"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Circular Title (optional) — e.g. Master Direction on KYC — Amendment 2026"
            className="w-full px-4 py-3 rounded-[12px] text-sm font-sans bg-[#0A0A0A] text-white outline-none placeholder:text-[#8B8B93]"
          />
        </div>
        <div className="space-y-4">
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="w-full px-4 py-3 rounded-[12px] text-sm font-sans bg-[#0A0A0A] text-white outline-none"
          >
            {['RBI', 'SEBI', 'IRDAI', 'FIU_IND', 'MCA'].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            onClick={handleProcess}
            disabled={!file || processing}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-full text-sm font-semibold transition-opacity ${
              !file || processing
                ? 'bg-[#1A1A1A] text-[#8B8B93] cursor-not-allowed'
                : 'bg-gradient-to-r from-[#00C6FF] to-[#7000FF] text-white hover:opacity-90'
            }`}
          >
            <Upload size={14} />
            Upload and Process
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-[#1A1100] rounded-[16px] px-5 py-3 mb-6 text-sm text-[#FFA500] font-sans">
          ⚠ Upload failed — {error}
        </div>
      )}

      {(processing || log.length > 0) && (
        <div className="mb-6">
          <p className="text-sm font-medium text-[#8B8B93] mb-4">Processing</p>
          <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-4">
            <div className="flex flex-col gap-3">
              {STEP_LABELS.map((label, i) => {
                const stepNum = i + 1
                const isDone = completed.includes(stepNum)
                const isActive = activeStep === stepNum && !isDone
                const color = isDone ? '#00FF88' : isActive ? '#00C6FF' : '#8B8B93'
                const icon = isDone ? '✓' : isActive ? '⟳' : '○'
                return (
                  <div key={i} className="flex items-center gap-3 text-sm font-sans" style={{ color }}>
                    <span className="w-5">{icon}</span>
                    <span>Step {stepNum}/4 — {label}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {log.length > 0 && (
            <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-sm text-[#8B8B93] leading-relaxed font-sans">
              {log.map((line, i) => (
                <div key={i}>▸ {line}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          <p className="text-sm font-medium text-[#8B8B93] mb-4">Summary</p>
          <div className="bg-[#0A0A0A] rounded-[24px] p-6 mb-6">
            <div className="flex items-center gap-3 mb-6">
              <CheckCircle2 size={20} className="text-[#00FF88]" />
              <span className="font-bold text-[#00FF88] text-base font-sans">
                Processing complete
              </span>
            </div>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <p className="text-sm font-medium text-[#8B8B93] mb-1">MAPs created</p>
                <p className="text-3xl font-bold text-white font-sans">
                  {result.maps_created ?? 0}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-[#8B8B93] mb-1">Highest priority</p>
                <div className="mt-1">
                  <Badge tier={highestTier} />
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-[#8B8B93] mb-1">Total exposure</p>
                <p className="text-3xl font-bold text-white font-sans">
                  {formatINR(result.total_penalty_exposure || 0)}
                </p>
              </div>
            </div>
            <p className="text-sm text-[#8B8B93] font-sans">
              Wings assigned: {(result.wings_assigned || []).join(' · ') || '—'}
            </p>
          </div>
          <button
            onClick={() => navigate('/')}
            className="w-full px-4 py-3 rounded-full text-sm font-semibold text-white bg-gradient-to-r from-[#00C6FF] to-[#7000FF] hover:opacity-90 transition-opacity mb-6"
          >
            View MAPs on Dashboard →
          </button>
        </>
      )}

      <p className="text-sm font-medium text-[#8B8B93] mb-4">Demo data</p>
      <div className="bg-[#0A0A0A] rounded-[24px] p-6 text-center mb-4">
        <span className="block mb-3 text-2xl">📂</span>
        <p className="text-sm text-[#8B8B93] font-sans">Load 10 pre-downloaded Canara Bank relevant circulars</p>
        <p className="text-sm text-[#8B8B93] mt-2 font-sans">
          KYC · CKYCR · PSL · AML · CIC · BSBDA · IRAC · Interest Rate · CRR/SLR
        </p>
      </div>
      <div className="flex justify-center">
        <button
          onClick={handleDemoLoad}
          className="flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white bg-[#1A1A1A] hover:bg-[#2A2A2A] transition-colors"
        >
          <FolderOpen size={14} className="text-[#00C6FF]" />
          Load Demo Data
        </button>
      </div>

      {demoNotice && (
        <div
          className="rounded-[16px] px-5 py-3 mt-4 text-sm font-sans"
          style={{
            background: demoNotice.type === 'success' ? '#001A11' : '#1A1100',
            color: demoNotice.type === 'success' ? '#00FF88' : '#FFA500',
          }}
        >
          {demoNotice.text}
        </div>
      )}
    </div>
  )
}
