import type { AnalysisResult } from '../../types'
import { MapPin } from 'lucide-react'
import EvidenceBadge from '../EvidenceBadge'

interface Props { result: AnalysisResult }

export default function BugLocationCard({ result }: Props) {
  const top = result.primary_predictions[0]

  if (!top) {
    return (
      <div className="card">
        <div className="card-header"><MapPin size={14} />Bug Location</div>
        <p className="text-gray-500 text-sm">No location identified.</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header"><MapPin size={14} />Bug Location</div>
      <div className="space-y-4">
        {/* Primary location */}
        <div className="bg-gray-800/60 rounded-lg p-4 border border-yellow-900/40">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1.5">
              <div>
                <span className="text-xs text-gray-500">File</span>
                <div className="font-mono text-sm text-blue-400 mt-0.5">{top.file}</div>
              </div>
              <div>
                <span className="text-xs text-gray-500">Function</span>
                <div className="font-mono text-sm text-yellow-300 mt-0.5">{top.function}()</div>
              </div>
              <div className="flex items-center gap-4">
                <div>
                  <span className="text-xs text-gray-500">Lines</span>
                  <div className="text-sm text-gray-300 mt-0.5">{top.line_start}–{top.line_end}</div>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Rank</span>
                  <div className="text-sm text-gray-300 mt-0.5">#1</div>
                </div>
              </div>
            </div>
            <EvidenceBadge strength={top.evidence_strength} />
          </div>
          <p className="text-xs text-gray-400 mt-3 leading-relaxed">{top.reason}</p>
        </div>

        {/* Quick list of other candidates */}
        {result.primary_predictions.length > 1 && (
          <div>
            <div className="text-xs text-gray-500 mb-2">Other candidates</div>
            <div className="space-y-1">
              {result.primary_predictions.slice(1, 5).map((p) => (
                <div key={p.rank} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-600 w-5">#{p.rank}</span>
                  <span className="font-mono text-blue-400/80 truncate">{p.file.split('/').pop()}</span>
                  <span className="text-gray-600">·</span>
                  <span className="font-mono text-yellow-300/70">{p.function}()</span>
                  <span className="ml-auto"><EvidenceBadge strength={p.evidence_strength} /></span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
