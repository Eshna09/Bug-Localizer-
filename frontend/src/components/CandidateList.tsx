import { useState } from 'react'
import type { PredictedLocation } from '../types'
import EvidenceBadge from './EvidenceBadge'
import CodeViewer from './CodeViewer'
import { ChevronDown, ChevronRight, MapPin } from 'lucide-react'

interface Props {
  predictions: PredictedLocation[]
  title?: string
}

export default function CandidateList({ predictions, title = 'Top Candidates' }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  if (!predictions.length) {
    return (
      <div className="card">
        <div className="card-header"><MapPin size={14} />{title}</div>
        <p className="text-gray-500 text-sm">No predictions available.</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header"><MapPin size={14} />{title}</div>
      <div className="space-y-2">
        {predictions.map((pred, idx) => (
          <div
            key={idx}
            className="border border-gray-800 rounded-lg overflow-hidden"
          >
            {/* Row header — click to expand code */}
            <button
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-800/50 transition-colors text-left"
              onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
            >
              <span className="text-xs font-mono text-gray-500 w-6 shrink-0">#{pred.rank}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-mono text-blue-400 truncate">{pred.file}</span>
                  <span className="text-gray-600">·</span>
                  <span className="text-sm font-mono text-yellow-300">{pred.function}()</span>
                  <span className="text-xs text-gray-600">
                    L{pred.line_start}–{pred.line_end}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{pred.reason}</p>
              </div>
              <EvidenceBadge strength={pred.evidence_strength} />
              {pred.source_code
                ? expandedIdx === idx
                  ? <ChevronDown size={14} className="text-gray-500 shrink-0" />
                  : <ChevronRight size={14} className="text-gray-500 shrink-0" />
                : null
              }
            </button>
            {/* Expanded code view */}
            {expandedIdx === idx && pred.source_code && (
              <div className="border-t border-gray-800 p-3">
                <CodeViewer
                  code={pred.source_code}
                  filePath={pred.file}
                  startLine={pred.line_start}
                  highlightLines={Array.from(
                    { length: pred.line_end - pred.line_start + 1 },
                    (_, i) => pred.line_start + i
                  )}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
