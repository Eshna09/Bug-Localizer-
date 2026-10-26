import type { ApproachSummary } from '../types'
import EvidenceBadge from './EvidenceBadge'
import { BarChart2 } from 'lucide-react'

const APPROACH_LABELS: Record<string, string> = {
  keyword: 'Keyword Search',
  structural: 'Structural Analysis',
  llm_only: 'LLM Only',
  rag_llm: 'RAG + LLM',
}

interface Props {
  summaries: ApproachSummary[]
}

export default function ApproachComparison({ summaries }: Props) {
  // Sort by rank (lower rank number = better prediction)
  const sorted = [...summaries].sort((a, b) => {
    const ra = a.top_prediction_rank ?? 999
    const rb = b.top_prediction_rank ?? 999
    return ra - rb
  })

  return (
    <div className="card">
      <div className="card-header"><BarChart2 size={14} />Approach Comparison</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-gray-500 border-b border-gray-800">
            <th className="text-left pb-2 font-medium">Approach</th>
            <th className="text-left pb-2 font-medium">Top Prediction</th>
            <th className="text-left pb-2 font-medium">Rank</th>
            <th className="text-left pb-2 font-medium">Evidence</th>
            <th className="text-right pb-2 font-medium">Latency</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {sorted.map((s) => (
            <tr key={s.approach} className="py-2">
              <td className="py-2.5 pr-4">
                <span className="font-medium text-gray-200">
                  {APPROACH_LABELS[s.approach] || s.approach}
                </span>
              </td>
              <td className="py-2.5 pr-4">
                {s.top_prediction_file ? (
                  <span className="font-mono text-xs text-blue-400">
                    {s.top_prediction_file.split('/').pop()}
                    <span className="text-gray-500">::</span>
                    <span className="text-yellow-400">{s.top_prediction_function}()</span>
                  </span>
                ) : (
                  <span className="text-gray-600 text-xs">{s.error || 'N/A'}</span>
                )}
              </td>
              <td className="py-2.5 pr-4">
                {s.top_prediction_rank != null
                  ? <span className="font-mono text-gray-300">#{s.top_prediction_rank}</span>
                  : <span className="text-gray-600">—</span>
                }
              </td>
              <td className="py-2.5 pr-4">
                {s.evidence_strength
                  ? <EvidenceBadge strength={s.evidence_strength} />
                  : <span className="text-gray-600">—</span>
                }
              </td>
              <td className="py-2.5 text-right">
                {s.latency_ms != null
                  ? <span className="font-mono text-xs text-gray-500">{s.latency_ms.toFixed(0)}ms</span>
                  : <span className="text-gray-600">—</span>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
