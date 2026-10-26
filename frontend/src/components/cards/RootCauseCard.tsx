import type { AnalysisResult } from '../../types'
import { Target, ArrowRight } from 'lucide-react'

interface Props { result: AnalysisResult }

export default function RootCauseCard({ result }: Props) {
  const rc = result.bug_explanation?.root_cause
  const affected = result.bug_explanation?.affected_components ?? []

  if (!rc) return null

  return (
    <div className="card">
      <div className="card-header"><Target size={14} />Root Cause Analysis</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Root cause */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Root Cause</div>
          <div className="bg-red-950/30 border border-red-900/40 rounded-lg p-3 space-y-1.5">
            <div className="font-mono text-sm text-blue-400">{rc.file}</div>
            <div className="font-mono text-sm text-yellow-300">{rc.function}()</div>
            <div className="text-xs text-gray-500">Lines {rc.line_start}–{rc.line_end}</div>
            <p className="text-xs text-gray-300 leading-relaxed pt-1">{rc.explanation}</p>
          </div>
        </div>

        {/* Affected components */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            Affected Components
          </div>
          {affected.length === 0 ? (
            <p className="text-gray-600 text-sm">None identified.</p>
          ) : (
            <div className="space-y-2">
              {affected.map((ac, i) => (
                <div
                  key={i}
                  className="bg-yellow-950/20 border border-yellow-900/30 rounded-lg p-3 space-y-1"
                >
                  <div className="flex items-center gap-1.5">
                    <ArrowRight size={12} className="text-yellow-600" />
                    <span className="font-mono text-xs text-blue-400">{ac.file}</span>
                    <span className="font-mono text-xs text-yellow-300">{ac.function}()</span>
                  </div>
                  <p className="text-xs text-gray-400 pl-4">{ac.how_affected}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
