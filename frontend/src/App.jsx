import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import BootAnimation from './components/BootAnimation'
import Dashboard from './pages/Dashboard'
import Mandates from './pages/Mandates'
import MapDetail from './pages/MapDetail'
import UploadCircular from './pages/UploadCircular'
import EvidenceUpload from './pages/EvidenceUpload'
import AuditTrail from './pages/AuditTrail'

export default function App() {
  const [booted, setBooted] = useState(false)

  function handleBootComplete() {
    setBooted(true)
  }

  if (!booted) {
    return <BootAnimation onComplete={handleBootComplete} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/mandates" element={<Mandates />} />
          <Route path="/map/:mapId" element={<MapDetail />} />
          <Route path="/upload-circular" element={<UploadCircular />} />
          <Route path="/evidence" element={<EvidenceUpload />} />
          <Route path="/audit-trail" element={<AuditTrail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
