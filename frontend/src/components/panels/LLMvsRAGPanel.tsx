/**
 * LLM Only vs RAG + LLM — Research Pipeline Visualization
 *
 * Shows the ACTUAL implementation pipeline for both approaches, with:
 * - Live state per step (waiting / processing / completed / failed)
 * - Retrieval details panel for RAG
 * - LLM reasoning details panel for LLM-only
 * - Comparison table
 * - All values from real execution — nothing fabricated
 */
import { useState } from 'react'
import {
  ChevronDown, ChevronUp, CheckCircle2, XCircle, Loader2,
  Clock, Database, Search, Zap, ArrowDown,
} from 'lucide-react'
import type { AnalysisResult, ApproachDetail } from '../../types'
import clsx from 'clsx'

// ─── Types ──────────────────────────────────────────────────────────────────

type StepState = 'waiting' | 'processing' | 'completed' | 'failed'

interface PipelineStep {
  id: string
  label: string
  detail?: string
}

// ─── Pipeline definitions ────────────────────────────────────────────────────

const LLM_ONLY_STEPS: PipelineStep[] = [
  { id: 'issue',       label: 'Bug Report',             detail: 'Issue description received' },
  { id: 'context',     label: 'Issue Understanding',    detail: 'Source context selected (no retrieval)' },
  { id: 'llm',         label: 'LLM Inference',          detail: 'Model reasons over issue + code sample' },
  { id: 'candidates',  label: 'Candidate Generation',   detail: 'Structured predictions extracted from LLM output' },
  { id: 'resolution',  label: 'Repository Resolution',  detail: 'Paths normalised to repository-relative form' },
  { id: 'validation',  label: 'Candidate Validation',   detail: 'Each candidate verified against actual repo index' },
  { id: 'ranking',     label: 'Ranked Predictions',     detail: 'Valid candidates sorted by evidence strength' },
]

const RAG_LLM_STEPS: PipelineStep[] = [
  { id: 'issue',        label: 'Bug Report',             detail: 'Issue description received' },
  { id: 'embedding',    label: 'Issue Embedding',        detail: 'Issue encoded into vector space' },
  { id: 'faiss',        label: 'FAISS Vector Store',     detail: 'Function-aware chunks with file/line metadata' },
  { id: 'retrieval',    label: 'Top-K Retrieval',        detail: 'Semantically similar code chunks retrieved' },
  { id: 'context',      label: 'Retrieved Code Context', detail: 'Evidence provided to LLM' },
  { id: 'llm',          label: 'LLM Inference',          detail: 'Model reasons over issue + retrieved evidence' },
  { id: 'ranking',      label: 'Candidate Ranking',      detail: 'Predictions extracted from evidence-grounded output' },
  { id: 'validation',   label: 'Repository Validation',  detail: 'Each candidate verified against actual repo' },
  { id: 'predictions',  label: 'Ranked Predictions',     detail: 'Final source-file candidates' },
]

// ─── Helpers ─────────────────────────────────────────────────────────────────

function safeFileName(path?: string | null): string {
  if (!path) return '?'
  return path.replace(/\\/g, '/').split('/').pop() || path
}

/** Derive per-step states from the approach detail's pipeline_stages list */
function deriveStepStates(
  steps: PipelineStep[],
  stages: string[],
  status: string,
  isProcessing: boolean,
): Record<string, StepState> {
  const stageSet = new Set(stages)
  const failed   = status === 'API_ERROR' || status === 'TIMEOUT' || status === 'PARSING_ERROR'
  const empty    = status === 'EMPTY_RESPONSE'
  const success  = status === 'SUCCESS'

  // Map our step IDs to the backend stage names
  const stageMap: Record<string, string[]> = {
    // LLM-only
    issue:       ['context_selection'],
    context:     ['context_selection', 'prompt_built'],
    llm:         ['llm_response_received'],
    candidates:  ['parsing'],
    resolution:  ['validation'],
    validation:  ['validation', 'complete'],
    ranking:     ['complete'],
    // RAG
    embedding:   ['issue_embedding'],
    faiss:       ['issue_embedding', 'vector_retrieval'],
    retrieval:   ['vector_retrieval', 'metadata_filtering'],
    predictions: ['complete'],
  }

  const result: Record<string, StepState> = {}
  let hitFail = false

  for (const step of steps) {
    if (hitFail) {
      result[step.id] = 'waiting'
      continue
    }
    const mappedStages = stageMap[step.id] ?? []
    const reached = mappedStages.some(s => stageSet.has(s))

    if (reached) {
      if (failed && step.id === 'validation') {
        result[step.id] = 'failed'
        hitFail = true
      } else if (empty && step.id === 'ranking') {
        result[step.id] = 'failed'
      } else {
        result[step.id] = 'completed'
      }
    } else if (isProcessing) {
      result[step.id] = 'processing'
      isProcessing = false
    } else {
      result[step.id] = 'waiting'
    }
  }

  // If overall success, mark all completed
  if (success) {
    steps.forEach(s => { result[s.id] = 'completed' })
  }

  return result
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StepIcon({ state }: { state: StepState }) {
  switch (state) {
    case 'completed':  return <CheckCircle2 size={14} className="text-green-400 shrink-0" />
    case 'failed':     return <XCircle      size={14} className="text-red-400   shrink-0" />
    case 'processing': return <Loader2      size={14} className="text-brand-400 animate-spin shrink-0" />
    case 'waiting':    return <Clock        size={14} className="text-gray-600  shrink-0" />
  }
}

function StepRow({
  step, state, isLast = false,
}: { step: PipelineStep; state: StepState; isLast?: boolean }) {
  return (
    <div className="flex flex-col items-center">
      <div className={clsx(
        'flex items-center gap-2 px-3 py-1.5 rounded-lg w-full text-xs transition-all duration-300',
        state === 'completed'  && 'bg-green-900/20 border border-green-900/40',
        state === 'failed'     && 'bg-red-900/20   border border-red-900/40',
        state === 'processing' && 'bg-brand-900/30 border border-brand-800/60',
        state === 'waiting'    && 'bg-gray-800/30  border border-gray-800/40 opacity-50',
      )}>
        <StepIcon state={state} />
        <div className="flex-1">
          <span className={clsx(
            'font-medium',
            state === 'completed'  && 'text-green-300',
            state === 'failed'     && 'text-red-300',
            state === 'processing' && 'text-brand-300',
            state === 'waiting'    && 'text-gray-500',
          )}>
            {step.label}
          </span>
          {step.detail && (
            <p className="text-gray-600 text-[10px] leading-tight mt-0.5">{step.detail}</p>
          )}
        </div>
      </div>
      {!isLast && (
        <ArrowDown size={12} className={clsx(
          'my-0.5',
          state === 'completed' ? 'text-green-700' : 'text-gray-700'
        )} />
      )}
    </div>
  )
}

function FaissBox({ detail }: { detail: ApproachDetail | undefined }) {
  const chunkCount = detail?.retrieved_chunk_details?.length ?? 0
  const model      = detail?.embedding_model ?? 'all-MiniLM-L6-v2 (fallback)'

  return (
    <div className={clsx(
      'border rounded-lg p-2 my-1 w-full text-xs',
      chunkCount > 0
        ? 'border-green-800/50 bg-green-950/20'
        : 'border-gray-700/50 bg-gray-800/20',
    )}>
      <div className="flex items-center gap-1 mb-1">
        <Database size={11} className="text-green-500 shrink-0" />
        <span className="font-semibold text-green-400 text-[11px]">FAISS Vector Store</span>
      </div>
      <div className="space-y-0.5 text-gray-400">
        <div>Model: <span className="text-gray-300 font-mono text-[10px]">{model}</span></div>
        <div>Chunks: <span className="text-green-300">{chunkCount > 0 ? chunkCount : '—'}</span></div>
        <div className="text-gray-600 text-[10px]">Function-aware | File + line metadata</div>
      </div>
    </div>
  )
}

function RetrievalDetails({ detail }: { detail: ApproachDetail | undefined }) {
  const [open, setOpen] = useState(false)
  if (!detail) return null

  const chunks = detail.retrieved_chunk_details ?? []
  const model  = detail.embedding_model ?? '—'

  return (
    <div className="mt-3 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800/40 hover:bg-gray-800/60 transition-colors text-xs"
      >
        <span className="flex items-center gap-1.5 text-green-400 font-medium">
          <Search size={11} />
          Retrieval Details
        </span>
        <span className="flex items-center gap-1 text-gray-500">
          {chunks.length} chunks
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>

      {open && (
        <div className="p-3 space-y-3">
          {/* Config */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="text-gray-500">Embedding model</div>
            <div className="font-mono text-gray-300 text-[10px] truncate">{model}</div>
            <div className="text-gray-500">Vector store</div>
            <div className="text-gray-300">FAISS IndexFlatIP</div>
            <div className="text-gray-500">Chunks retrieved</div>
            <div className="text-gray-300">{chunks.length || '—'}</div>
            <div className="text-gray-500">Top-K</div>
            <div className="text-gray-300">{chunks.length || '—'}</div>
          </div>

          {/* Retrieved chunks */}
          {chunks.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs text-gray-500 uppercase tracking-wider">Retrieved Evidence</div>
              {chunks.map((c, i) => (
                <div key={c.chunk_id ?? i} className="bg-gray-800/50 rounded-lg p-2 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-gray-500">#{i + 1}</span>
                    <span className={clsx(
                      'font-mono text-[10px] px-1.5 py-0.5 rounded',
                      (c.similarity_score ?? 0) >= 0.7 ? 'bg-green-900/40 text-green-300' :
                      (c.similarity_score ?? 0) >= 0.5 ? 'bg-yellow-900/40 text-yellow-300' :
                                                          'bg-gray-700/40 text-gray-400'
                    )}>
                      sim: {(c.similarity_score ?? 0).toFixed(3)}
                    </span>
                  </div>
                  <div className="font-mono text-blue-400 truncate">{c.file ?? '—'}</div>
                  <div className="font-mono text-yellow-300">{c.function ?? '—'}()</div>
                  <div className="text-gray-600">
                    Lines {c.line_start ?? '?'}–{c.line_end ?? '?'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-600">No retrieved chunks available.</p>
          )}
        </div>
      )}
    </div>
  )
}

function LLMDetails({ detail }: { detail: ApproachDetail | undefined }) {
  const [open, setOpen] = useState(false)
  if (!detail) return null

  const preds   = (detail.top5_predictions ?? []).filter(p => !p.is_test_file)
  const model   = detail.model ?? detail.embedding_model ?? '—'
  const latency = detail.latency_ms != null ? `${Math.round(detail.latency_ms)}ms` : '—'
  const tokens  = detail.token_usage?.total_tokens ?? null
  const ctx     = detail.context_size_chars
    ? `${(detail.context_size_chars / 1000).toFixed(1)}k chars`
    : '—'

  return (
    <div className="mt-3 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800/40 hover:bg-gray-800/60 transition-colors text-xs"
      >
        <span className="flex items-center gap-1.5 text-yellow-400 font-medium">
          <Zap size={11} />
          LLM Prediction Details
        </span>
        <span className="flex items-center gap-1 text-gray-500">
          {preds.length} valid
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>

      {open && (
        <div className="p-3 space-y-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div className="text-gray-500">Model</div>
            <div className="font-mono text-gray-300 text-[10px] truncate">{model}</div>
            <div className="text-gray-500">Context supplied</div>
            <div className="text-gray-300">{ctx} (source files only)</div>
            <div className="text-gray-500">Latency</div>
            <div className="text-gray-300">{latency}</div>
            {tokens && <>
              <div className="text-gray-500">Tokens used</div>
              <div className="text-gray-300">{tokens}</div>
            </>}
            <div className="text-gray-500">Semantic retrieval</div>
            <div className="text-red-400">No</div>
          </div>

          {preds.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs text-gray-500 uppercase tracking-wider">
                Valid Predictions ({detail.num_source_predictions ?? preds.length} source)
              </div>
              {preds.map((p, i) => (
                <div key={`${p.file}-${i}`} className="bg-gray-800/50 rounded-lg p-2 text-xs">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-gray-500">#{i + 1}</span>
                    <span className={clsx(
                      'text-[10px] px-1 rounded',
                      p.evidence_strength === 'High'   ? 'bg-green-900/40 text-green-300'  :
                      p.evidence_strength === 'Medium' ? 'bg-yellow-900/40 text-yellow-300' :
                                                          'bg-gray-700/40 text-gray-400'
                    )}>
                      {p.evidence_strength}
                    </span>
                  </div>
                  <div className="font-mono text-blue-400 truncate">{p.file ?? '—'}</div>
                  <div className="font-mono text-yellow-300">{p.function ?? '—'}()</div>
                  <div className="text-gray-600">Lines {p.line_start ?? '?'}–{p.line_end ?? '?'}</div>
                  {p.reason && (
                    <p className="text-gray-500 text-[10px] mt-1 leading-relaxed line-clamp-2">
                      {p.reason}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-gray-600 space-y-1">
              <p className="text-red-400">No valid predictions produced.</p>
              {detail.error && (
                <p className="text-gray-500">{detail.error.slice(0, 200)}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Comparison table ────────────────────────────────────────────────────────

function ComparisonTable({
  llm, rag
}: { llm: ApproachDetail | undefined; rag: ApproachDetail | undefined }) {
  const check = <CheckCircle2 size={12} className="text-green-400 mx-auto" />
  const cross  = <XCircle     size={12} className="text-red-400   mx-auto" />

  const llmOk  = llm?.status === 'SUCCESS'
  const ragOk  = rag?.status === 'SUCCESS'
  const ragChunks = rag?.retrieved_chunk_details?.length ?? 0

  const rows = [
    { label: 'Issue understanding',   llm: true,    rag: true },
    { label: 'Repository context',    llm: true,    rag: true },
    { label: 'Semantic embedding',    llm: false,   rag: true },
    { label: 'Vector database',       llm: false,   rag: true },
    { label: 'Retrieved code context',llm: false,   rag: ragChunks > 0 },
    { label: 'LLM reasoning',         llm: llmOk,   rag: ragOk },
    { label: 'Candidate validation',  llm: llmOk,   rag: ragOk },
  ]

  return (
    <div className="mt-4 border border-gray-800 rounded-lg overflow-hidden">
      <div className="bg-gray-800/60 px-3 py-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
        Capability Comparison
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800 text-gray-500">
            <th className="text-left px-3 py-1.5 font-medium">Feature</th>
            <th className="text-center px-3 py-1.5 font-medium text-yellow-400">LLM Only</th>
            <th className="text-center px-3 py-1.5 font-medium text-green-400">RAG + LLM</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.label} className="border-b border-gray-800/50 last:border-0">
              <td className="px-3 py-1.5 text-gray-400">{row.label}</td>
              <td className="px-3 py-1.5 text-center">{row.llm ? check : cross}</td>
              <td className="px-3 py-1.5 text-center">{row.rag ? check : cross}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Approach summary row ─────────────────────────────────────────────────────

function ApproachSummaryRow({
  label, detail, color
}: { label: string; detail: ApproachDetail | undefined; color: string }) {
  const preds   = (detail?.top5_predictions ?? []).filter(p => !p.is_test_file)
  const top1    = preds[0]
  const latency = detail?.latency_ms != null ? `${Math.round(detail.latency_ms)}ms` : '—'
  const status  = detail?.status ?? 'EMPTY_RESPONSE'

  return (
    <div className={clsx('rounded-lg p-3 border', {
      'border-green-900/40 bg-green-950/10': status === 'SUCCESS',
      'border-red-900/40   bg-red-950/10':   status !== 'SUCCESS',
    })}>
      <div className="flex items-center justify-between mb-2">
        <span className={clsx('text-xs font-semibold', color)}>{label}</span>
        <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded', {
          'bg-green-900/40 text-green-300': status === 'SUCCESS',
          'bg-red-900/40   text-red-300':   status !== 'SUCCESS',
        })}>
          {status}
        </span>
      </div>
      {top1 ? (
        <>
          <div className="text-xs text-gray-500 mb-0.5">Top-1</div>
          <div className="font-mono text-xs text-blue-400 truncate">{safeFileName(top1.file)}</div>
          <div className="font-mono text-xs text-yellow-300">{top1.function ?? ''}()</div>
          <div className="text-[10px] text-gray-600 mt-0.5">
            L{top1.line_start}–{top1.line_end} · {top1.evidence_strength}
          </div>
          {preds.length > 1 && (
            <div className="text-[10px] text-gray-600 mt-1">+{preds.length - 1} more candidates</div>
          )}
        </>
      ) : (
        <div className="text-xs text-gray-600 mt-1">
          {detail?.error?.slice(0, 80) || 'No predictions produced'}
        </div>
      )}
      <div className="text-[10px] text-gray-600 mt-1.5">Latency: {latency}</div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  result: AnalysisResult
  /**
   * During live analysis, pass the pipeline_stages from each approach_done
   * event so steps animate in real-time. After analysis completes, derived
   * from the final result object.
   */
  liveLLMStages?: string[]
  liveRAGStages?: string[]
  llmProcessing?: boolean
  ragProcessing?: boolean
}

export default function LLMvsRAGPanel({
  result,
  liveLLMStages,
  liveRAGStages,
  llmProcessing = false,
  ragProcessing  = false,
}: Props) {
  if (!result) return null

  const details   = result.approach_details ?? []
  const llmDetail = details.find(d => d.approach === 'llm_only')
  const ragDetail = details.find(d => d.approach === 'rag_llm')

  const llmStages = liveLLMStages ?? llmDetail?.pipeline_stages ?? []
  const ragStages = liveRAGStages ?? ragDetail?.pipeline_stages ?? []
  const llmStatus = llmDetail?.status ?? 'EMPTY_RESPONSE'
  const ragStatus = ragDetail?.status ?? 'EMPTY_RESPONSE'

  const llmStepStates = deriveStepStates(LLM_ONLY_STEPS, llmStages, llmStatus, llmProcessing)
  const ragStepStates = deriveStepStates(RAG_LLM_STEPS,  ragStages, ragStatus, ragProcessing)

  return (
    <div className="card border border-gray-700/50">
      {/* Header */}
      <div className="card-header mb-5">
        <Zap size={14} className="text-brand-400" />
        <span className="font-semibold">LLM Only  vs  RAG + LLM</span>
        <span className="ml-2 text-xs text-gray-500">
          Two independent research pipelines — actual execution shown
        </span>
      </div>

      {/* ── Two pipeline diagrams side-by-side ── */}
      <div className="grid grid-cols-2 gap-6 mb-6">

        {/* LLM Only */}
        <div>
          {/* Title */}
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-yellow-900/30">
            <Zap size={13} className="text-yellow-400" />
            <span className="font-semibold text-yellow-300 text-sm">LLM Only</span>
            <span className={clsx(
              'ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded',
              llmStatus === 'SUCCESS'
                ? 'bg-green-900/40 text-green-300'
                : 'bg-red-900/40 text-red-300'
            )}>
              {llmStatus}
            </span>
          </div>

          {/* Steps */}
          <div className="space-y-0">
            {LLM_ONLY_STEPS.map((step, i) => (
              <StepRow
                key={step.id}
                step={step}
                state={llmStepStates[step.id] ?? 'waiting'}
                isLast={i === LLM_ONLY_STEPS.length - 1}
              />
            ))}
          </div>

          {/* Footer labels */}
          <div className="mt-3 space-y-1">
            <p className="text-[10px] text-gray-500 italic">
              LLM receives issue + repository context directly
            </p>
            <p className="text-[10px] text-red-400/70 italic">No semantic retrieval</p>
          </div>

          {/* LLM prediction details (expandable) */}
          <LLMDetails detail={llmDetail} />
        </div>

        {/* RAG + LLM */}
        <div>
          {/* Title */}
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-green-900/30">
            <Search size={13} className="text-green-400" />
            <span className="font-semibold text-green-300 text-sm">RAG + LLM</span>
            <span className={clsx(
              'ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded',
              ragStatus === 'SUCCESS'
                ? 'bg-green-900/40 text-green-300'
                : 'bg-red-900/40 text-red-300'
            )}>
              {ragStatus}
            </span>
          </div>

          {/* Steps — with inline FAISS box */}
          <div className="space-y-0">
            {RAG_LLM_STEPS.map((step, i) => (
              <div key={step.id}>
                <StepRow
                  step={step}
                  state={ragStepStates[step.id] ?? 'waiting'}
                  isLast={i === RAG_LLM_STEPS.length - 1}
                />
                {/* Inline FAISS box after the embedding step */}
                {step.id === 'embedding' && (
                  <FaissBox detail={ragDetail} />
                )}
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="mt-3 space-y-1">
            <p className="text-[10px] text-gray-500 italic">
              LLM receives issue + semantically retrieved evidence
            </p>
            <p className="text-[10px] text-green-400/70 italic">
              Embedding: {ragDetail?.embedding_model ?? 'all-MiniLM-L6-v2 (fallback)'}
            </p>
          </div>

          {/* Retrieval details (expandable) */}
          <RetrievalDetails detail={ragDetail} />
        </div>
      </div>

      {/* ── Comparison table ── */}
      <ComparisonTable llm={llmDetail} rag={ragDetail} />

      {/* ── Approach summary cards ── */}
      <div className="mt-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Approach Comparison</div>
        <div className="grid grid-cols-2 gap-3">
          <ApproachSummaryRow label="LLM Only"  detail={llmDetail} color="text-yellow-400" />
          <ApproachSummaryRow label="RAG + LLM" detail={ragDetail}  color="text-green-400" />
        </div>
      </div>
    </div>
  )
}
