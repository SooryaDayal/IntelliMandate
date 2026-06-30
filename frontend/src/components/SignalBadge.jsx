import { signalMeta } from '../lib/format'

export default function SignalBadge({ signalType }) {
  const { cls, label } = signalMeta(signalType)
  return <span className={`signal-badge ${cls}`}>{label}</span>
}
