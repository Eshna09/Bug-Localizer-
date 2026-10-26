import { AlertTriangle, ArrowRight, Shield, TestTube2 } from 'lucide-react'
import type { BugExplanation, AnalysisResult } from '../../types'

interface Props {
  explanation: BugExplanation
  result: AnalysisResult
}

export default function RootCausePanel({ explanation, result }: Props) {
  if (!explanation) return null

  const rc = explanation.root_cause
  const rcFile = rc?.file ?? ''
  const isTestFile = rcFile
    ? (rcFile.includes('/test') || rcFile.includes('\\test') ||
       rcFile.startsWith('test_') || rcFile.endsWith('_test.py'))
    : false

  const testEvidence = (result.primary_predictions ?? []).filter(p => p.is_test_file)
  const affectedComponents = explanation.affected_components ?? []
  const dependencyChain    = explanation.dependency_chain ?? []

  return (
    <div className="card border border-gray-700/50">
      <div className="card-header mb-4">
        <AlertTriangle size={14} className="text-red-400" />
        Root Cause Analysis
      </div>

      <div className="space-y-4">

        {/* Root Cause */}
        <div>
          <div className="text-xs text-red-400 uppercase tracking-wider mb-2 font-semibold">Root Cause</div>
          {rc && rcFile && !isTestFile ? (
            <div className="bg-red-950/20 border border-red-900/40 rounded-lg p-3">
              <div className="font-mono text-sm text-blue-400">{rcFile}</div>
              <div className="font-mono text-sm text-yellow-300">{rc.function ?? ''}()</div>
              <div className="text-xs text-gray-500 mt-0.5">
                Lines {rc.line_start ?? '?'}–{rc.line_end ?? '?'}
              </div>
              {rc.explanation && (
                <p className="text-sm text-gray-300 mt-2 leading-relaxed">{rc.explanation}</p>
              )}
            </div>
          ) : (
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 text-sm text-gray-400">
              {explanation.what_is_wrong || 'Root cause not determined'}
            </div>
          )}
        </div>

        {/* Why */}
        {explanation.why_is_it_wrong && (
          <div>
            <div className="text-xs text-orange-400 uppercase tracking-wider mb-2 font-semibold">Why</div>
            <p className="text-sm text-gray-300 leading-relaxed">{explanation.why_is_it_wrong}</p>
          </div>
        )}

        {/* Expected vs Actual */}
        {(explanation.what_should_happen || explanation.what_actually_happens) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="bg-green-950/20 border border-green-900/30 rounded-lg p-3">
              <div className="text-xs text-green-400 uppercase tracking-wider mb-1 font-semibold">Expected</div>
              <p className="text-xs text-gray-300 leading-relaxed">
                {explanation.what_should_happen || '—'}
              </p>
            </div>
            <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-3">
              <div className="text-xs text-red-400 uppercase tracking-wider mb-1 font-semibold">Actual</div>
              <p className="text-xs text-gray-300 leading-relaxed">
                {explanation.what_actually_happens || '—'}
              </p>
            </div>
          </div>
        )}

        {/* Dependency chain */}
        {dependencyChain.length > 0 && (
          <div>
            <div className="text-xs text-purple-400 uppercase tracking-wider mb-2 font-semibold">
              Dependency Chain
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {dependencyChain.map((step, i) => (
                <span key={i} className="flex items-center gap-1">
                  <span className="text-xs bg-gray-800 text-gray-300 px-2 py-1 rounded font-mono">
                    {String(step)}
                  </span>
                  {i < dependencyChain.length - 1 && (
                    <ArrowRight size={12} className="text-gray-600" />
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Affected components */}
        {affectedComponents.length > 0 && (
          <div>
            <div className="text-xs text-yellow-400 uppercase tracking-wider mb-2 font-semibold">
              Affected Components
            </div>
            <div className="space-y-1.5">
              {affectedComponents.map((comp, i) => {
                if (!comp) return null
                const compFile = comp.file ?? ''
                return (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <Shield size={11} className="text-yellow-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="font-mono text-blue-400">
                        {compFile.split('/').pop() || compFile}
                      </span>
                      <span className="text-gray-600">::</span>
                      <span className="font-mono text-yellow-300">{comp.function ?? ''}()</span>
                      {comp.how_affected && (
                        <span className="text-gray-500 ml-2">{comp.how_affected}</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Supporting test evidence */}
        {testEvidence.length > 0 && (
          <div className="border-t border-gray-800 pt-3">
            <div className="text-xs text-orange-400 uppercase tracking-wider mb-2 font-semibold flex items-center gap-1">
              <TestTube2 size={11} />
              Supporting Test Evidence
              <span className="text-gray-600 font-normal ml-1">(test files — not root cause)</span>
            </div>
            <div className="space-y-1">
              {testEvidence.map((p, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <TestTube2 size={11} className="text-orange-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="font-mono text-orange-300">
                      {(p.file ?? '').split('/').pop()}
                    </span>
                    <span className="text-gray-600">::</span>
                    <span className="font-mono text-gray-400">{p.function ?? ''}()</span>
                    {p.reason && (
                      <p className="text-gray-600 mt-0.5">{p.reason.slice(0, 100)}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Downstream impact */}
        {explanation.downstream_impact && (
          <div className="border-t border-gray-800 pt-3">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1 font-semibold">
              Downstream Impact
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">{explanation.downstream_impact}</p>
          </div>
        )}
      </div>
    </div>
  )
}
