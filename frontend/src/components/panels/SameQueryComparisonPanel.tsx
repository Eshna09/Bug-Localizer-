/**
 * SameQueryComparisonPanel
 *
 * The central research comparison: LLM Only vs RAG+LLM on the SAME query.
 * Shows every measurable metric side-by-side, with honest N/A for anything
 * that cannot be computed from the current run.
 *
 * Research integrity rules:
 *  - Never fabricate values.
 *  - "N/A – reason" shown for unavailable metrics.
 *  - Hallucination Rate derived from rejected_predictions count (transparent methodology).
 *  - Resource metrics from psutil (CPU/memory); GPU always N/A.
 */
import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import type { AnalysisResult, ApproachDetail } from '../../types'
import clsx from 'clsx'

// ─── helpers ────────────────────────────────────────────────────────────────

function na(reason?: string): string {
  return reason ? `N/A – ${reason}` : 'N/A'
}

function fmt(v: number | null | undefined, decimals = 1, suffix = ''): string {
  if (v == null) return na('not measured')
  return `${v.toFixed(decimals)}${suffix}`
}

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return na('not measured')
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)} min`
  if (ms >= 1000)  return `${(ms / 1000).toFixed(1)} s`
  return `${Math.round(ms)} ms`
}

function hallucination_rate(detail: ApproachDetail | undefined): string {
  if (!detail) return na('approach not run')
  const rejected = detail.rejected_predictions?.length ?? 0
  const total    = (detail.num_source_predictions + detail.num_test_predictions + rejected)
  if (total === 0) return na('no predictions produced')
  const rate = (rejected / total) * 100
  return `${rate.toFixed(0)}% (${rejected}/${total} predictions rejected by repo validation)`
}

function mrr(detail: ApproachDetail | undefined): string {
  if (!detail) return na('approach not run')
  const preds = (detail.top5_predictions ?? []).filter(p => !p.is_test_file)
  if (!preds.length) return na('no source predictions')
  // Without ground truth we can only report 1/rank_of_top1 = 1/1 (preliminary)
  return `${(1 / (preds[0].rank || 1)).toFixed(3)} (preliminary — 1/top-1 rank, no ground truth)`
}

// ─── row types ───────────────────────────────────────────────────────────────

interface MetricSection {
  title: string
  color: string
  rows: { label: string; llm: string; rag: string; note?: string }[]
}

function buildSections(
  llm: ApproachDetail | undefined,
  rag: ApproachDetail | undefined,
): MetricSection[] {
  const llmPreds = (llm?.top5_predictions ?? []).filter(p => !p.is_test_file)
  const ragPreds = (rag?.top5_predictions ?? []).filter(p => !p.is_test_file)
  const llmTok   = llm?.token_usage
  const ragTok   = rag?.token_usage
  const llmRes   = llm?.resource_usage
  const ragRes   = rag?.resource_usage
  const ragChunks = rag?.retrieved_chunk_details ?? []

  return [
    {
      title: 'Localization Results',
      color: 'text-blue-400',
      rows: [
        {
          label: 'Execution Status',
          llm:   llm?.status ?? na('not run'),
          rag:   rag?.status ?? na('not run'),
        },
        {
          label: 'Source Predictions',
          llm:   llm ? `${llm.num_source_predictions}` : na('not run'),
          rag:   rag ? `${rag.num_source_predictions}` : na('not run'),
        },
        {
          label: 'Top-1 Candidate',
          llm:   llmPreds[0]
            ? `${llmPreds[0].file.split('/').pop()}::${llmPreds[0].function}()`
            : na('no source predictions'),
          rag:   ragPreds[0]
            ? `${ragPreds[0].file.split('/').pop()}::${ragPreds[0].function}()`
            : na('no source predictions'),
        },
        {
          label: 'Top-1 Confidence',
          llm:   llmPreds[0]?.evidence_strength ?? na('no prediction'),
          rag:   ragPreds[0]?.evidence_strength ?? na('no prediction'),
        },
        {
          label: 'Top-3 Candidates',
          llm:   llmPreds.length >= 1
            ? llmPreds.slice(0,3).map(p => p.file.split('/').pop()).join(', ')
            : na('no predictions'),
          rag:   ragPreds.length >= 1
            ? ragPreds.slice(0,3).map(p => p.file.split('/').pop()).join(', ')
            : na('no predictions'),
        },
        {
          label: 'MRR (preliminary)',
          llm:   mrr(llm),
          rag:   mrr(rag),
          note:  'True MRR requires ground truth. Value shown is 1/rank_of_top1 for this run only.',
        },
      ],
    },
    {
      title: 'Retrieval & Evidence',
      color: 'text-green-400',
      rows: [
        {
          label: 'Semantic Retrieval',
          llm:   'No',
          rag:   rag ? 'Yes' : na('not run'),
        },
        {
          label: 'Embedding Model',
          llm:   na('no embedding — direct context'),
          rag:   rag?.embedding_model ?? na('not recorded'),
        },
        {
          label: 'Retrieved Chunks',
          llm:   '0 (no vector retrieval)',
          rag:   rag ? `${ragChunks.length}` : na('not run'),
        },
        {
          label: 'Context Supplied',
          llm:   llm?.context_size_chars
            ? `${(llm.context_size_chars / 1000).toFixed(1)}k chars (static sample)`
            : na('not recorded'),
          rag:   rag?.context_size_chars
            ? `${(rag.context_size_chars / 1000).toFixed(1)}k chars (retrieved)`
            : na('not recorded'),
        },
        {
          label: 'Retrieval Quality',
          llm:   na('not applicable — no retrieval'),
          rag:   ragChunks.length > 0
            ? `Top similarity: ${ragChunks[0].similarity_score.toFixed(3)} | ${ragChunks.length} chunks`
            : na('no chunks retrieved'),
        },
        {
          label: 'Retrieval Recall@K',
          llm:   na('not applicable'),
          rag:   na('requires ground truth — run experiment for full metrics'),
        },
      ],
    },
    {
      title: 'Quality & Hallucination',
      color: 'text-yellow-400',
      rows: [
        {
          label: 'Hallucination Rate',
          llm:   hallucination_rate(llm),
          rag:   hallucination_rate(rag),
          note:  'Methodology: predictions rejected by repository index validation / total LLM predictions.',
        },
        {
          label: 'Valid Predictions',
          llm:   llm ? `${llm.num_source_predictions + llm.num_test_predictions}` : na('not run'),
          rag:   rag ? `${rag.num_source_predictions + rag.num_test_predictions}` : na('not run'),
        },
        {
          label: 'Rejected Predictions',
          llm:   llm ? `${llm.rejected_predictions?.length ?? 0}` : na('not run'),
          rag:   rag ? `${rag.rejected_predictions?.length ?? 0}` : na('not run'),
        },
        {
          label: 'Evidence Grounded',
          llm:   'No — static code sample, no retrieved evidence',
          rag:   rag?.status === 'SUCCESS' && ragChunks.length > 0
            ? 'Yes — predictions grounded in retrieved chunks'
            : na('RAG did not produce retrieved evidence'),
        },
        {
          label: 'Accuracy / Correctness',
          llm:   na('requires ground truth — run ShopBug experiment'),
          rag:   na('requires ground truth — run ShopBug experiment'),
          note:  'Accuracy is calculated by the Evaluation module after predictions vs ground truth.',
        },
        {
          label: 'Precision',
          llm:   na('requires ground truth'),
          rag:   na('requires ground truth'),
        },
        {
          label: 'Recall',
          llm:   na('requires ground truth'),
          rag:   na('requires ground truth'),
        },
      ],
    },
    {
      title: 'Performance',
      color: 'text-purple-400',
      rows: [
        {
          label: 'Latency (wall clock)',
          llm:   fmtMs(llm?.latency_ms),
          rag:   fmtMs(rag?.latency_ms),
        },
        {
          label: 'Input Tokens',
          llm:   llmTok ? `${llmTok.prompt_tokens}` : na('provider did not return token usage'),
          rag:   ragTok ? `${ragTok.prompt_tokens}` : na('provider did not return token usage'),
        },
        {
          label: 'Output Tokens',
          llm:   llmTok ? `${llmTok.completion_tokens}` : na('provider did not return token usage'),
          rag:   ragTok ? `${ragTok.completion_tokens}` : na('provider did not return token usage'),
        },
        {
          label: 'Total Tokens',
          llm:   llmTok ? `${llmTok.total_tokens}` : na('provider did not return token usage'),
          rag:   ragTok ? `${ragTok.total_tokens}` : na('provider did not return token usage'),
        },
        {
          label: 'CPU (avg %)',
          llm:   fmt(llmRes?.cpu_avg_percent, 1, '%'),
          rag:   fmt(ragRes?.cpu_avg_percent, 1, '%'),
          note:  llmRes?.measurement_note ?? 'Measured via psutil process sampling every 200ms.',
        },
        {
          label: 'CPU (peak %)',
          llm:   fmt(llmRes?.cpu_peak_percent, 1, '%'),
          rag:   fmt(ragRes?.cpu_peak_percent, 1, '%'),
        },
        {
          label: 'Memory RSS (peak)',
          llm:   fmt(llmRes?.memory_rss_mb_peak, 0, ' MB'),
          rag:   fmt(ragRes?.memory_rss_mb_peak, 0, ' MB'),
        },
        {
          label: 'Memory Delta',
          llm:   fmt(llmRes?.memory_delta_mb, 0, ' MB'),
          rag:   fmt(ragRes?.memory_delta_mb, 0, ' MB'),
          note:  'Peak RSS during call minus RSS before call.',
        },
        {
          label: 'GPU Utilization',
          llm:   llmRes?.gpu_utilization ?? na('no GPU monitoring dependency installed'),
          rag:   ragRes?.gpu_utilization ?? na('no GPU monitoring dependency installed'),
          note:  'GPU monitoring requires gputil or pynvml — not currently installed.',
        },
      ],
    },
    {
      title: 'Generated Fix',
      color: 'text-orange-400',
      rows: [
        {
          label: 'Test-Pass Rate',
          llm:   na('requires Docker verification — enable run_verification'),
          rag:   na('requires Docker verification — enable run_verification'),
          note:  'Enable Docker verification in the analysis request to populate this metric.',
        },
        {
          label: 'Fix Success',
          llm:   na('requires verification'),
          rag:   na('requires verification'),
        },
      ],
    },
  ]
}

// ─── table row ────────────────────────────────────────────────────────────────

function MetricRow({
  label, llm, rag, note, isNA,
}: { label: string; llm: string; rag: string; note?: string; isNA?: boolean }) {
  const [expanded, setExpanded] = useState(false)

  const llmIsNA = llm.startsWith('N/A')
  const ragIsNA = rag.startsWith('N/A')

  return (
    <>
      <tr className="border-b border-gray-800/40 hover:bg-gray-800/20 transition-colors">
        <td className="px-3 py-2 text-xs text-gray-400 align-top">
          <div className="flex items-center gap-1">
            {label}
            {note && (
              <button onClick={() => setExpanded(v => !v)}
                className="text-gray-600 hover:text-gray-400 transition-colors ml-1">
                {expanded ? <ChevronUp size={10}/> : <ChevronDown size={10}/>}
              </button>
            )}
          </div>
        </td>
        <td className={clsx('px-3 py-2 text-xs align-top max-w-[220px]', llmIsNA ? 'text-gray-600' : 'text-yellow-300')}>
          {llm}
        </td>
        <td className={clsx('px-3 py-2 text-xs align-top max-w-[220px]', ragIsNA ? 'text-gray-600' : 'text-green-300')}>
          {rag}
        </td>
      </tr>
      {expanded && note && (
        <tr className="border-b border-gray-800/40">
          <td colSpan={3} className="px-3 py-1.5 text-[10px] text-gray-600 italic bg-gray-800/20">
            ℹ {note}
          </td>
        </tr>
      )}
    </>
  )
}

// ─── main ─────────────────────────────────────────────────────────────────────

interface Props { result: AnalysisResult }

export default function SameQueryComparisonPanel({ result }: Props) {
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['Localization Results', 'Retrieval & Evidence']))
  const details = result.approach_details ?? []
  const llm = details.find(d => d.approach === 'llm_only')
  const rag = details.find(d => d.approach === 'rag_llm')

  const sections = buildSections(llm, rag)

  function toggle(title: string) {
    setOpenSections(prev => {
      const next = new Set(prev)
      next.has(title) ? next.delete(title) : next.add(title)
      return next
    })
  }

  return (
    <div className="card border border-gray-700/50">
      {/* Header */}
      <div className="card-header mb-4">
        <AlertTriangle size={14} className="text-brand-400" />
        <span className="font-semibold">LLM Only vs RAG + LLM — Same Query Comparison</span>
        <span className="ml-2 text-xs text-gray-500">
          Identical repository + issue submitted to both approaches
        </span>
      </div>

      {/* Approach labels */}
      <div className="flex gap-4 mb-4 text-xs">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-yellow-900/40 bg-yellow-950/10">
          <span className="w-2 h-2 rounded-full bg-yellow-400 shrink-0"/>
          <span className="font-semibold text-yellow-300">LLM Only</span>
          <span className="text-gray-500">— direct reasoning, no retrieval</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-green-900/40 bg-green-950/10">
          <span className="w-2 h-2 rounded-full bg-green-400 shrink-0"/>
          <span className="font-semibold text-green-300">RAG + LLM</span>
          <span className="text-gray-500">— embedding + retrieval + reasoning</span>
        </div>
      </div>

      {/* Issue confirmation */}
      <div className="bg-gray-800/40 border border-gray-700 rounded-lg p-3 mb-4 text-xs">
        <div className="text-gray-500 mb-1 uppercase tracking-wider text-[10px]">Issue submitted to both approaches</div>
        <p className="text-gray-300 leading-relaxed">{result.issue_description}</p>
        <div className="flex gap-4 mt-2 text-gray-500">
          <span>Repo: <span className="text-gray-300 font-mono text-[10px]">{result.repo_url}</span></span>
          <span>Commit: <span className="text-gray-300 font-mono">{result.commit_hash?.slice(0,8) ?? '—'}</span></span>
        </div>
      </div>

      {/* Collapsible metric sections */}
      {sections.map(section => (
        <div key={section.title} className="mb-2 border border-gray-800 rounded-lg overflow-hidden">
          <button
            onClick={() => toggle(section.title)}
            className="w-full flex items-center justify-between px-3 py-2 bg-gray-800/50 hover:bg-gray-800/70 transition-colors"
          >
            <span className={clsx('text-xs font-semibold', section.color)}>{section.title}</span>
            {openSections.has(section.title)
              ? <ChevronUp size={13} className="text-gray-500"/>
              : <ChevronDown size={13} className="text-gray-500"/>}
          </button>

          {openSections.has(section.title) && (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-[10px] text-gray-500">
                  <th className="text-left px-3 py-1.5 font-medium w-[35%]">Metric</th>
                  <th className="text-left px-3 py-1.5 font-medium text-yellow-500 w-[32%]">LLM Only</th>
                  <th className="text-left px-3 py-1.5 font-medium text-green-500 w-[33%]">RAG + LLM</th>
                </tr>
              </thead>
              <tbody>
                {section.rows.map(row => (
                  <MetricRow key={row.label} {...row} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}

      <p className="text-[10px] text-gray-600 mt-3 italic">
        Metrics marked N/A are not fabricated. They require either ground truth (run the Evaluation experiment)
        or Docker verification (enable run_verification). All displayed values come from actual execution.
      </p>
    </div>
  )
}
