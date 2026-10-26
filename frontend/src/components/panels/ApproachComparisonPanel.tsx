import { BarChart2, CheckCircle2, AlertCircle, Clock, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import type { AnalysisResult, ApproachDetail, PredictedLocation } from '../../types'
import clsx from 'clsx'

const APPROACH_META: Record<string, {
  label: string; color: string; badgeClass: string; description: string; pipeline: string[]
}> = {
  keyword: {
    label: 'Keyword Search', color: 'blue',
    badgeClass: 'bg-blue-900/50 text-blue-300 border border-blue-800',
    description: 'TF-IDF keyword scoring across function names, file names, and source code. No LLM. Fast and deterministic.',
    pipeline: ['Issue text', '→ Keyword extraction', '→ Score all functions', '→ Rank by score'],
  },
  structural: {
    label: 'Structural Analysis', color: 'purple',
    badgeClass: 'bg-purple-900/50 text-purple-300 border border-purple-800',
    description: 'Seed functions via keywords, expand via call graph BFS. Captures indirect bugs through dependency chains.',
    pipeline: ['Issue text', '→ Seed identification', '→ Call graph BFS', '→ Rank by proximity'],
  },
  llm_only: {
    label: 'LLM Only', color: 'yellow',
    badgeClass: 'bg-yellow-900/50 text-yellow-300 border border-yellow-800',
    description: 'LLM reasons over a static sample of source code. No vector retrieval — measures pure LLM capability.',
    pipeline: ['Issue text', '→ Source code sample', '→ LLM reasoning', '→ Validated predictions'],
  },
  rag_llm: {
    label: 'RAG + LLM', color: 'green',
    badgeClass: 'bg-green-900/50 text-green-300 border border-green-800',
    description: 'Embeds the issue, retrieves semantically similar chunks via FAISS, expands with dependencies, then LLM reasons over evidence.',
    pipeline: ['Issue text', '→ Embedding', '→ FAISS retrieval', '→ Dep. expansion', '→ LLM + evidence', '→ Validated'],
  },
}

const STATUS_STYLE: Record<string, { text: string; bg: string }> = {
  SUCCESS:        { text: 'text-green-300',  bg: 'bg-green-900/30 border border-green-800' },
  TIMEOUT:        { text: 'text-red-300',    bg: 'bg-red-900/30 border border-red-800' },
  API_ERROR:      { text: 'text-red-300',    bg: 'bg-red-900/30 border border-red-800' },
  PARSING_ERROR:  { text: 'text-orange-300', bg: 'bg-orange-900/30 border border-orange-800' },
  EMPTY_RESPONSE: { text: 'text-gray-400',   bg: 'bg-gray-800/50 border border-gray-700' },
}

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.EMPTY_RESPONSE
  const icon = status === 'SUCCESS'
    ? <CheckCircle2 size={11} />
    : status === 'TIMEOUT'
    ? <Clock size={11} />
    : status === 'API_ERROR'
    ? <XCircle size={11} />
    : <AlertCircle size={11} />
  return (
    <span className={clsx('flex items-center gap-1 text-xs font-mono px-1.5 py-0.5 rounded', s.text, s.bg)}>
      {icon}
      {status || '?'}
    </span>
  )
}

// Safe file name extractor — never crashes on null/undefined
function fileName(path?: string | null): string {
  if (!path) return '?'
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || path
}

function PredictionRow({ pred, rank }: { pred: PredictedLocation; rank: number }) {
  if (!pred) return null
  const strengthColor: Record<string, string> = {
    High: 'text-green-400', Medium: 'text-yellow-400',
    Low: 'text-orange-400', Insufficient: 'text-gray-500',
  }
  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-gray-800/50 last:border-0">
      <span className="font-mono text-xs text-gray-600 w-5 shrink-0">#{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-xs text-blue-400 truncate">{fileName(pred.file)}</div>
        <div className="font-mono text-xs text-yellow-300">{pred.function ?? ''}()</div>
        <div className="text-xs text-gray-600">
          L{pred.line_start ?? '?'}–{pred.line_end ?? '?'}
          {pred.is_test_file && (
            <span className="ml-2 text-orange-400 text-[10px] uppercase tracking-wider">test</span>
          )}
        </div>
      </div>
      <span className={clsx('text-xs shrink-0', strengthColor[pred.evidence_strength] ?? 'text-gray-500')}>
        {pred.evidence_strength ?? '—'}
      </span>
    </div>
  )
}

function ApproachCard({ detail }: { detail: ApproachDetail }) {
  const [expanded, setExpanded] = useState(false)
  if (!detail) return null
  const meta = APPROACH_META[detail.approach]
  if (!meta) return null

  // defensive: both top5_predictions and supporting_evidence may be missing on SSE payloads
  const allPreds    = (detail.top5_predictions ?? (detail as any).predictions ?? []) as PredictedLocation[]
  const sourcePreds = allPreds.filter(p => !p.is_test_file)
  const testPreds   = (detail.supporting_evidence ?? allPreds.filter(p => p.is_test_file)).slice(0, 3)
  const stages      = detail.pipeline_stages ?? []

  const borderColor: Record<string, string> = {
    blue: 'border-blue-900/40', purple: 'border-purple-900/40',
    yellow: 'border-yellow-900/40', green: 'border-green-900/40',
  }

  const latencyStr = detail.latency_ms != null
    ? `${Math.round(detail.latency_ms)}ms`
    : null

  return (
    <div className={clsx('card border', borderColor[meta.color])}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className={clsx('text-xs px-2 py-0.5 rounded font-medium', meta.badgeClass)}>
          {meta.label}
        </span>
        <StatusBadge status={detail.status ?? 'EMPTY_RESPONSE'} />
        {latencyStr && (
          <span className="ml-auto font-mono text-xs text-gray-500">{latencyStr}</span>
        )}
      </div>

      <p className="text-xs text-gray-500 mb-3 leading-relaxed">{meta.description}</p>

      {/* Pipeline steps */}
      <div className="flex flex-wrap gap-1 mb-3">
        {meta.pipeline.map((step, i) => (
          <span key={i} className={clsx(
            'text-[10px] px-1.5 py-0.5 rounded',
            i === 0 ? 'bg-gray-700 text-gray-300' : 'text-gray-500'
          )}>
            {step}
          </span>
        ))}
      </div>

      {/* Counts */}
      <div className="flex gap-3 text-xs mb-3 flex-wrap">
        <span className="text-green-400">
          {detail.num_source_predictions ?? sourcePreds.length} source candidates
        </span>
        {(detail.num_test_predictions ?? testPreds.length) > 0 && (
          <span className="text-orange-400">
            +{detail.num_test_predictions ?? testPreds.length} test evidence
          </span>
        )}
        {detail.context_size_chars != null && (
          <span className="text-gray-600">
            {(detail.context_size_chars / 1000).toFixed(1)}k ctx
          </span>
        )}
        {detail.token_usage?.total_tokens && (
          <span className="text-gray-600">{detail.token_usage.total_tokens} tok</span>
        )}
      </div>

      {/* Top-1 */}
      {sourcePreds[0] ? (
        <div className="bg-gray-800/50 rounded-lg p-2 mb-2">
          <div className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Top-1 Candidate</div>
          <div className="font-mono text-sm text-blue-400 truncate">
            {fileName(sourcePreds[0].file)}
          </div>
          <div className="font-mono text-sm text-yellow-300">{sourcePreds[0].function ?? ''}()</div>
          <div className="text-xs text-gray-500 mt-0.5">
            L{sourcePreds[0].line_start ?? '?'}–{sourcePreds[0].line_end ?? '?'} ·
            <span className={clsx('ml-1', {
              'text-green-400':  sourcePreds[0].evidence_strength === 'High',
              'text-yellow-400': sourcePreds[0].evidence_strength === 'Medium',
              'text-orange-400': sourcePreds[0].evidence_strength === 'Low',
              'text-gray-500':   !sourcePreds[0].evidence_strength ||
                                  sourcePreds[0].evidence_strength === 'Insufficient',
            })}>
              {sourcePreds[0].evidence_strength ?? '—'}
            </span>
          </div>
        </div>
      ) : (
        <div className="bg-gray-800/30 rounded-lg p-2 mb-2 text-xs text-gray-600">
          {detail.error
            ? <span className="text-red-400">{String(detail.error).slice(0, 80)}</span>
            : 'No source predictions'}
        </div>
      )}

      {/* Expand for Top-5 */}
      {sourcePreds.length > 1 && (
        <>
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Hide' : `Show Top-${Math.min(sourcePreds.length, 5)}`}
          </button>
          {expanded && (
            <div className="mt-2">
              {sourcePreds.slice(1, 5).map((p, i) => (
                <PredictionRow key={`${p.file}-${p.function}-${i}`} pred={p} rank={i + 2} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Supporting evidence */}
      {testPreds.length > 0 && expanded && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <div className="text-xs text-orange-500 mb-1 uppercase tracking-wider">
            Supporting Evidence (test files)
          </div>
          {testPreds.map((p, i) => (
            <PredictionRow key={`${p.file}-${p.function}-${i}`} pred={p} rank={i + 1} />
          ))}
        </div>
      )}

      {/* Pipeline stages */}
      {stages.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <div className="flex flex-wrap gap-1">
            {stages.map((s, i) => (
              <span key={i} className="text-[10px] bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded font-mono">
                ✓ {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface Props { result: AnalysisResult }

export default function ApproachComparisonPanel({ result }: Props) {
  if (!result) return null
  const details = result.approach_details ?? []

  const getDetail = (approach: string): ApproachDetail => {
    const d = details.find(d => d.approach === approach)
    if (d) return d
    const s = result.approach_summaries?.find(s => s.approach === approach)
    const preds: PredictedLocation[] = ((result as any)[`${approach}_predictions`] ?? [])
    return {
      approach,
      status: (s?.error ? 'EMPTY_RESPONSE' : 'SUCCESS') as any,
      latency_ms: s?.latency_ms,
      top5_predictions: preds.filter(p => !p.is_test_file).slice(0, 5),
      supporting_evidence: preds.filter(p => p.is_test_file).slice(0, 3),
      retrieved_chunk_details: [],
      pipeline_stages: [],
      num_source_predictions: preds.filter(p => !p.is_test_file).length,
      num_test_predictions: preds.filter(p => p.is_test_file).length,
      error: s?.error,
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <BarChart2 size={16} className="text-brand-400" />
        <h2 className="font-semibold text-gray-100">Localization Approach Comparison</h2>
        <span className="text-xs text-gray-500">
          4 independent approaches — production source files only as primary candidates
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(['keyword', 'structural', 'llm_only', 'rag_llm'] as const).map(approach => (
          <ApproachCard key={approach} detail={getDetail(approach)} />
        ))}
      </div>
    </div>
  )
}
