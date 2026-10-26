import { Trophy } from 'lucide-react'
import type { AnalysisResult, PredictedLocation } from '../../types'
import clsx from 'clsx'

const RANK_COLORS = ['text-yellow-300', 'text-gray-300', 'text-orange-400', 'text-gray-400', 'text-gray-500']
const RANK_BG    = [
  'bg-yellow-900/20 border-yellow-800/40',
  'bg-gray-800/40 border-gray-700/40',
  'bg-orange-900/10 border-orange-900/30',
  'bg-gray-800/30 border-gray-800',
  'bg-gray-800/20 border-gray-800',
]

const STRENGTH_COLOR: Record<string, string> = {
  High:         'text-green-400 bg-green-900/30 border-green-800',
  Medium:       'text-yellow-400 bg-yellow-900/30 border-yellow-800',
  Low:          'text-orange-400 bg-orange-900/30 border-orange-800',
  Insufficient: 'text-gray-500 bg-gray-800/30 border-gray-700',
}

function RankCard({ pred, rank }: { pred: PredictedLocation; rank: number }) {
  if (!pred) return null
  const fileParts = (pred.file ?? '').replace(/\\/g, '/').split('/')
  const fname = fileParts[fileParts.length - 1] || pred.file || '?'
  return (
    <div className={clsx('border rounded-lg p-3 flex items-start gap-3', RANK_BG[rank - 1] ?? RANK_BG[4])}>
      <div className={clsx('text-2xl font-bold shrink-0', RANK_COLORS[rank - 1] ?? RANK_COLORS[4])}>
        #{rank}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-sm text-blue-400 truncate" title={pred.file ?? ''}>{fname}</div>
        <div className="font-mono text-sm text-yellow-300">{pred.function ?? ''}()</div>
        {pred.class_name && (
          <div className="text-xs text-gray-500">Class: {pred.class_name}</div>
        )}
        <div className="text-xs text-gray-500 mt-0.5">
          Lines {pred.line_start ?? '?'}–{pred.line_end ?? '?'}
        </div>
        <p className="text-xs text-gray-400 mt-1 leading-relaxed line-clamp-2">{pred.reason ?? ''}</p>
      </div>
      <div className="shrink-0">
        <span className={clsx(
          'text-xs px-2 py-0.5 rounded border',
          STRENGTH_COLOR[pred.evidence_strength] ?? STRENGTH_COLOR.Insufficient
        )}>
          {pred.evidence_strength}
        </span>
      </div>
    </div>
  )
}

interface Props { result: AnalysisResult }

export default function Top5RankingPanel({ result }: Props) {
  // Use primary predictions (already filtered to source files)
  const primary = result.primary_predictions?.filter(p => !p.is_test_file) ?? []

  if (!primary.length) return null

  // Determine which approach contributed the primary predictions
  const contributingApproach = (() => {
    const d = result.approach_details
    if (!d) return 'best available'
    if (result.rag_llm_predictions?.some(p => !p.is_test_file)) return 'RAG + LLM'
    if (result.llm_only_predictions?.some(p => !p.is_test_file)) return 'LLM Only'
    if (result.structural_predictions?.some(p => !p.is_test_file)) return 'Structural Analysis'
    return 'Keyword Search'
  })()

  return (
    <div className="card">
      <div className="card-header mb-4">
        <Trophy size={14} className="text-yellow-400" />
        Final Localization Ranking
        <span className="ml-2 text-xs text-gray-500">
          Source: {contributingApproach} — production files only
        </span>
      </div>

      <div className="space-y-2">
        {primary.slice(0, 5).map((pred, i) => (
          <RankCard key={pred.file + pred.function + i} pred={pred} rank={i + 1} />
        ))}
      </div>

      {primary.length > 5 && (
        <p className="text-xs text-gray-600 mt-2 text-center">
          +{primary.length - 5} additional candidates
        </p>
      )}
    </div>
  )
}
