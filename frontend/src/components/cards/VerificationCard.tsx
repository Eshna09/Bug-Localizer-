import type { VerificationResult } from '../../types'
import { FlaskConical, CheckCircle, XCircle, AlertCircle, HelpCircle } from 'lucide-react'
import VerificationBadge from '../VerificationBadge'

interface Props { verification: VerificationResult }

const TestStatus = ({ status }: { status: string }) => {
  const icons: Record<string, React.ReactNode> = {
    PASSED: <CheckCircle size={12} className="text-green-400" />,
    FAILED: <XCircle size={12} className="text-red-400" />,
    ERROR: <AlertCircle size={12} className="text-yellow-400" />,
    SKIPPED: <HelpCircle size={12} className="text-gray-500" />,
  }
  return <span className="flex items-center gap-1">{icons[status] || null}{status}</span>
}

export default function VerificationCard({ verification }: Props) {
  return (
    <div className="card">
      <div className="card-header"><FlaskConical size={14} />Verification</div>

      {/* Status */}
      <div className="flex items-center gap-3 mb-5">
        <VerificationBadge status={verification.status} />
        {verification.docker_used && (
          <span className="text-xs text-gray-600">Docker sandbox</span>
        )}
      </div>

      {/* Before / After reproduction test */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-2">Before Fix</div>
          <div className="text-sm font-semibold">
            Reproduction Test:{' '}
            <span className={verification.reproduction_test_before === 'PASSED' ? 'text-green-400' : 'text-red-400'}>
              {verification.reproduction_test_before || 'N/A'}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {verification.passed_before} passed / {verification.failed_before} failed
          </div>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-2">After Fix</div>
          <div className="text-sm font-semibold">
            Reproduction Test:{' '}
            <span className={verification.reproduction_test_after === 'PASSED' ? 'text-green-400' : 'text-red-400'}>
              {verification.reproduction_test_after || 'N/A'}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {verification.passed_after} passed / {verification.failed_after} failed
          </div>
        </div>
      </div>

      {/* Test lists */}
      {(verification.tests_before.length > 0 || verification.tests_after.length > 0) && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Relevant Tests — Before</div>
            <div className="space-y-1">
              {verification.tests_before.map((t, i) => (
                <div key={i} className="text-xs flex items-center gap-2">
                  <TestStatus status={t.status} />
                  <span className="font-mono text-gray-400 truncate">{t.name}</span>
                </div>
              ))}
              {verification.tests_before.length === 0 && (
                <span className="text-gray-600 text-xs">No test results.</span>
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Relevant Tests — After</div>
            <div className="space-y-1">
              {verification.tests_after.map((t, i) => (
                <div key={i} className="text-xs flex items-center gap-2">
                  <TestStatus status={t.status} />
                  <span className="font-mono text-gray-400 truncate">{t.name}</span>
                </div>
              ))}
              {verification.tests_after.length === 0 && (
                <span className="text-gray-600 text-xs">No test results.</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Notes */}
      {verification.notes && (
        <p className="text-xs text-gray-500 mt-4 pt-3 border-t border-gray-800">
          {verification.notes}
        </p>
      )}
    </div>
  )
}
