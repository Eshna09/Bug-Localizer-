import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import type { VerificationResult } from '../../types'
import clsx from 'clsx'

interface Props { verification: VerificationResult }

export default function VerificationPanel({ verification: v }: Props) {
  const statusColor = {
    VERIFIED:               'text-green-400 border-green-900/50',
    PARTIALLY_VERIFIED:     'text-yellow-400 border-yellow-900/50',
    NOT_VERIFIED:           'text-red-400 border-red-900/50',
    VERIFICATION_UNAVAILABLE:'text-gray-500 border-gray-700',
  }[v.status] ?? 'text-gray-400'

  return (
    <div className={clsx('card border', statusColor)}>
      <div className="card-header mb-3">
        {v.status === 'VERIFIED' ? <CheckCircle2 size={14} className="text-green-400" />
          : v.status === 'NOT_VERIFIED' ? <XCircle size={14} className="text-red-400" />
          : <AlertCircle size={14} className="text-yellow-400" />}
        Verification
        <span className={clsx('ml-2 text-xs font-semibold', statusColor.split(' ')[0])}>{v.status}</span>
        {v.docker_used && <span className="ml-2 text-xs text-gray-600">Docker sandbox</span>}
      </div>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-gray-500 mb-1">Before fix</div>
          <div className="text-green-400">✓ {v.passed_before} passed</div>
          {v.failed_before > 0 && <div className="text-red-400">✗ {v.failed_before} failed</div>}
        </div>
        <div>
          <div className="text-gray-500 mb-1">After fix</div>
          <div className="text-green-400">✓ {v.passed_after} passed</div>
          {v.failed_after > 0 && <div className="text-red-400">✗ {v.failed_after} failed</div>}
        </div>
      </div>
      {v.notes && <p className="text-xs text-gray-500 mt-2">{v.notes}</p>}
    </div>
  )
}
