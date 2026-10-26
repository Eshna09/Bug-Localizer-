import { Wrench } from 'lucide-react'
import type { ProposedFix } from '../../types'

interface Props { fix: ProposedFix }

export default function ProposedFixPanel({ fix }: Props) {
  // Defensive: ensure fix object has required fields
  if (!fix || !fix.file) return null

  const fileName = (fix.file ?? '').split('/').pop() ?? fix.file
  const currentCode  = fix.current_code  ?? ''
  const proposedCode = fix.proposed_code ?? ''
  const whatChanged  = fix.what_changed  ?? []

  return (
    <div className="card border border-blue-900/40">
      <div className="card-header mb-4">
        <Wrench size={14} className="text-blue-400" />
        Proposed Fix
        <span className="ml-auto text-xs text-gray-500">
          {fileName} :: {fix.function ?? ''}()
        </span>
      </div>

      <div className="space-y-4">

        {fix.minimal_change_description && (
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Summary</div>
            <p className="text-sm text-gray-300 leading-relaxed">{fix.minimal_change_description}</p>
          </div>
        )}

        {fix.why_this_fixes && (
          <div>
            <div className="text-xs text-green-400 uppercase tracking-wider mb-2">Why This Fixes It</div>
            <p className="text-sm text-gray-300 leading-relaxed">{fix.why_this_fixes}</p>
          </div>
        )}

        {whatChanged.length > 0 && (
          <div>
            <div className="text-xs text-yellow-400 uppercase tracking-wider mb-2">Changes</div>
            <ul className="space-y-1">
              {whatChanged.map((c, i) => (
                <li key={i} className="text-xs text-gray-400 flex items-start gap-2">
                  <span className="text-yellow-600 shrink-0">•</span>
                  <span className="font-mono">{String(c)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {(currentCode || proposedCode) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-3">
              <div className="text-xs text-red-400 uppercase tracking-wider mb-2">Current Code</div>
              <pre className="text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-60">
                {currentCode || '(not available)'}
              </pre>
            </div>
            <div className="bg-green-950/20 border border-green-900/30 rounded-lg p-3">
              <div className="text-xs text-green-400 uppercase tracking-wider mb-2">Proposed Code</div>
              <pre className="text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-60">
                {proposedCode || '(not available)'}
              </pre>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {fix.why_safe && (
            <div>
              <span className="text-gray-500">Safety: </span>
              <span className="text-gray-400">{fix.why_safe}</span>
            </div>
          )}
          {fix.potential_side_effects && (
            <div>
              <span className="text-gray-500">Side effects: </span>
              <span className="text-gray-400">{fix.potential_side_effects}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
