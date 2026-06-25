export function formatINR(amount) {
  if (!amount) return '₹0'
  const n = Number(amount)
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(1)}Cr`
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(1)}L`
  return `₹${n.toLocaleString('en-IN')}`
}

export function daysRemaining(deadlineStr) {
  if (!deadlineStr) return null
  const dl = new Date(deadlineStr)
  if (isNaN(dl.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  dl.setHours(0, 0, 0, 0)
  return Math.round((dl - today) / (1000 * 60 * 60 * 24))
}

export function deadlineLabel(deadlineStr) {
  const d = daysRemaining(deadlineStr)
  if (d === null) return { text: '—', color: 'var(--text3)' }
  if (d < 0) return { text: `⚠ ${Math.abs(d)}d overdue`, color: 'var(--critical)' }
  if (d === 0) return { text: '⚠ Due today', color: 'var(--critical)' }
  if (d <= 7) return { text: `${d}d left`, color: 'var(--high)' }
  if (d <= 30) return { text: `${d}d left`, color: 'var(--medium)' }
  return { text: `${d}d left`, color: 'var(--text3)' }
}

export function tierClass(tier) {
  return (tier || 'low').toLowerCase()
}

export function tierColorHex(tier) {
  const map = {
    CRITICAL: '#f43f5e',
    HIGH: '#f97316',
    MEDIUM: '#eab308',
    LOW: '#22c55e',
  }
  return map[(tier || 'LOW').toUpperCase()] || '#3b82f6'
}

export function statusColor(status) {
  const map = {
    OPEN: 'var(--critical)',
    IN_PROGRESS: 'var(--medium)',
    CLOSED: 'var(--low)',
  }
  return map[(status || '').toUpperCase()] || 'var(--text3)'
}

export function signalMeta(signalType) {
  const map = {
    MANDATORY_IMMEDIATE: { cls: 'sig-mandatory-immediate', label: 'MANDATORY · IMMEDIATE' },
    MANDATORY_FUTURE: { cls: 'sig-mandatory-future', label: 'MANDATORY · FUTURE' },
    CIRCULAR_AMENDMENT: { cls: 'sig-amendment', label: 'AMENDMENT' },
    ADVISORY: { cls: 'sig-advisory', label: 'ADVISORY' },
    CONSULTATION_PAPER: { cls: 'sig-consultation', label: 'CONSULTATION' },
  }
  return map[(signalType || '').toUpperCase()] || { cls: 'sig-advisory', label: signalType || 'UNKNOWN' }
}

export function sourceColor(source) {
  const map = {
    RBI: '#3b82f6',
    SEBI: '#f97316',
    FIU: '#a78bfa',
    FIU_IND: '#a78bfa',
    IRDAI: '#22c55e',
    MCA: '#eab308',
  }
  return map[(source || '').toUpperCase()] || '#8a96a8'
}

export function truncate(str, n) {
  if (!str) return ''
  return str.length > n ? str.slice(0, n) + '...' : str
}