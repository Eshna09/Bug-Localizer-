import { useState } from 'react'
import { analyzeRepositoryStream, type ProgressEvent } from '../api/client'
import type { AnalysisResult, PredictedLocation, BugExplanation, ProposedFix, RepoStats } from '../types'
import { Bug, Loader2, AlertCircle, Github, FileText, CheckCircle2, Clock } from 'lucide-react'
import Dashboard from '../components/Dashboard'
import clsx from 'clsx'

const EXAMPLE_REPO  = 'https://github.com/tanurag-shrivastava/AstroLive'
const EXAMPLE_ISSUE = 'The API key is not showing any response when calling the NASA API.'

// Pipeline stages shown in the live progress panel
const STAGES = [
  { key: 'cloning',       label: 'Repository cloned',         phase: 'parse' },
  { key: 'parsing',       label: 'Files scanned',             phase: 'parse' },
  { key: 'localizing',    label: 'Functions extracted',       phase: 'parse' },
  { key: 'embedding',     label: 'Dependency graph + index',  phase: 'index' },
  { key: 'llm_only',      label: 'LLM-only localization',     phase: 'llm' },
  { key: 'rag_llm',       label: 'RAG + LLM localization',    phase: 'llm' },
  { key: 'explanation',   label: 'Root cause explanation',    phase: 'explain' },
  { key: 'fix',           label: 'Fix proposal',              phase: 'explain' },
]

const APPROACH_LABELS: Record<string, string> = {
  keyword: 'Keyword Search',
  structural: 'Structural Analysis',
  llm_only: 'LLM Only',
  rag_llm: 'RAG + LLM',
}

const STATUS_COLOR: Record<string, string> = {
  SUCCESS:        'text-green-400',
  TIMEOUT:        'text-red-400',
  API_ERROR:      'text-red-400',
  PARSING_ERROR:  'text-orange-400',
  EMPTY_RESPONSE: 'text-gray-500',
}

interface ApproachLive {
  count: number
  sourceCount: number
  ms?: number
  status?: string
  error?: string
  topFile?: string
  topFunction?: string
  pipelineStages?: string[]
}

interface LiveState {
  currentStage:    string
  currentMessage:  string
  completedStages: Set<string>
  approachResults: Record<string, ApproachLive>
  partialPredictions: PredictedLocation[]
  partialExplanation: BugExplanation | null
  partialFix:      ProposedFix | null
  language:        string
  functions:       number
  sourceFiles:     number
  testFiles:       number
  commitHash:      string
  indexedChunks:   number
  repoStats:       RepoStats | null
  llmPipeline:     string[]
  ragPipeline:     string[]
  // Live pipeline stages for the LLM vs RAG visualization
  liveLLMStages:   string[]
  liveRAGStages:   string[]
  llmProcessing:   boolean
  ragProcessing:   boolean
}

const initialLive: LiveState = {
  currentStage:    '',
  currentMessage:  '',
  completedStages: new Set(),
  approachResults: {},
  partialPredictions: [],
  partialExplanation: null,
  partialFix:      null,
  language:        '',
  functions:       0,
  sourceFiles:     0,
  testFiles:       0,
  commitHash:      '',
  indexedChunks:   0,
  repoStats:       null,
  llmPipeline:     [],
  ragPipeline:     [],
  liveLLMStages:   [],
  liveRAGStages:   [],
  llmProcessing:   false,
  ragProcessing:   false,
}

export default function BugAnalysisPage() {
  const [repoUrl,   setRepoUrl]   = useState('')
  const [issueText, setIssueText] = useState('')
  const [loading,   setLoading]   = useState(false)
  const [result,    setResult]    = useState<AnalysisResult | null>(null)
  const [error,     setError]     = useState<string | null>(null)
  const [live,      setLive]      = useState<LiveState>(initialLive)

  function handleProgress(event: ProgressEvent) {
    setLive(prev => {
      const next = { ...prev, completedStages: new Set(prev.completedStages) }

      if (event.message)            next.currentMessage = event.message
      if (event.detected_language)  next.language       = event.detected_language
      if (event.total_functions)    next.functions      = event.total_functions
      if (event.source_files)       next.sourceFiles    = event.source_files
      if (event.test_files)         next.testFiles      = event.test_files
      if (event.commit_hash)        next.commitHash     = event.commit_hash.slice(0, 8)
      if (event.indexed_chunks)     next.indexedChunks  = event.indexed_chunks

      if (event.stage) {
        next.currentStage = event.stage
        const idx = STAGES.findIndex(s => s.key === event.stage)
        if (idx > 0) {
          STAGES.slice(0, idx).forEach(s => next.completedStages.add(s.key))
        }
      }

      // repo_stats event
      if (event.type === 'repo_stats') {
        next.repoStats = event as any as RepoStats
      }

      // approach_done
      if (event.type === 'approach_done' && event.approach) {
        const preds = (event.predictions ?? []) as PredictedLocation[]
        const sourcePreds = preds.filter(p => !p.is_test_file)
        next.approachResults = {
          ...prev.approachResults,
          [event.approach]: {
            count:          preds.length,
            sourceCount:    sourcePreds.length,
            ms:             event.latency_ms,
            status:         event.status ?? 'SUCCESS',
            error:          event.error,
            topFile:        event.top_file,
            topFunction:    event.top_function,
            pipelineStages: event.pipeline_stages ?? [],
          },
        }
        if (event.approach === 'keyword')    next.completedStages.add('localizing')
        if (event.approach === 'structural') next.completedStages.add('localizing')
        if (event.approach === 'llm_only') {
          next.completedStages.add('llm_only')
          next.liveLLMStages  = event.pipeline_stages ?? []
          next.llmProcessing  = false
        }
        if (event.approach === 'rag_llm') {
          next.completedStages.add('rag_llm')
          next.liveRAGStages  = event.pipeline_stages ?? []
          next.ragProcessing  = false
        }
      }

      if (event.type === 'predictions_ready' && event.primary_predictions) {
        next.partialPredictions = (event.primary_predictions as PredictedLocation[]).filter(p => !p.is_test_file)
        next.completedStages.add('localizing')
        next.completedStages.add('llm_only')
        next.completedStages.add('rag_llm')
      }

      if (event.type === 'explanation_done' && event.bug_explanation) {
        next.partialExplanation = event.bug_explanation
        next.completedStages.add('explanation')
      }

      if (event.type === 'fix_done' && event.proposed_fix) {
        next.partialFix = event.proposed_fix
        next.completedStages.add('fix')
      }

      if (event.type === 'progress' && event.stage === 'embedding_done') {
        next.completedStages.add('embedding')
        if (event.indexed_chunks) next.indexedChunks = event.indexed_chunks
      }

      if (event.type === 'progress' && event.pipeline) {
        if (event.stage === 'llm_only') {
          next.llmPipeline  = event.pipeline
          next.llmProcessing = true
        }
        if (event.stage === 'rag_llm')  {
          next.ragPipeline  = event.pipeline
          next.ragProcessing = true
        }
      }

      return next
    })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!repoUrl.trim() || !issueText.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    setLive(initialLive)
    try {
      const data = await analyzeRepositoryStream(
        { repo_url: repoUrl.trim(), issue_description: issueText.trim(), run_verification: false },
        handleProgress,
      )
      setResult(data)
    } catch (err: any) {
      let msg: string = err?.message || 'Analysis failed.'
      if (msg.includes('exit code(128)') || msg.includes('Repository not found')) {
        msg = `Repository not found: ${repoUrl.trim()}\n\nMake sure the URL is correct and the repository is public.`
      } else if (msg.includes('No source files')) {
        msg = 'No supported source files found. Supported: Python, JavaScript, TypeScript.'
      } else if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('CORS')) {
        msg = 'Cannot connect to backend at localhost:8000. Make sure the backend server is running.'
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const stageStatus = (key: string) => {
    if (live.completedStages.has(key)) return 'done'
    if (live.currentStage === key || live.currentStage === key + '_done') return 'active'
    return 'pending'
  }

  return (
    <div className="space-y-5">
      {/* ── Input form ────────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header"><Bug size={14} />Bug Analysis</div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">GitHub Repository URL</label>
            <div className="relative">
              <Github size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="url"
                value={repoUrl}
                onChange={e => setRepoUrl(e.target.value)}
                placeholder="https://github.com/username/repository"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                required disabled={loading}
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Issue / Bug Description</label>
            <div className="relative">
              <FileText size={15} className="absolute left-3 top-3 text-gray-500" />
              <textarea
                value={issueText}
                onChange={e => setIssueText(e.target.value)}
                placeholder="Describe the bug you're seeing..."
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 resize-none"
                required disabled={loading}
              />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => { setRepoUrl(EXAMPLE_REPO); setIssueText(EXAMPLE_ISSUE) }}
              className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
              disabled={loading}
            >
              Use example →
            </button>
            <button type="submit" disabled={loading || !repoUrl || !issueText} className="btn-primary flex items-center gap-2">
              {loading
                ? <><Loader2 size={16} className="animate-spin" />Analyzing...</>
                : <><Bug size={16} />Analyze Bug</>}
            </button>
          </div>
        </form>
      </div>

      {/* ── Live progress panel ───────────────────────────────────── */}
      {loading && (
        <div className="card">
          <div className="card-header">
            <Loader2 size={14} className="animate-spin text-brand-400" />
            Live Pipeline Progress
          </div>

          {live.currentMessage && (
            <p className="text-sm text-brand-300 mb-4 font-medium">{live.currentMessage}</p>
          )}

          {/* Repo metadata */}
          {(live.language || live.commitHash) && (
            <div className="flex flex-wrap gap-4 text-xs text-gray-500 mb-4">
              {live.commitHash  && <span>Commit: <span className="font-mono text-gray-300">{live.commitHash}</span></span>}
              {live.language    && <span>Language: <span className="text-gray-300 capitalize">{live.language}</span></span>}
              {live.functions > 0 && <span>Functions: <span className="text-gray-300">{live.functions}</span></span>}
              {live.sourceFiles > 0 && <span>Source: <span className="text-blue-400">{live.sourceFiles}</span></span>}
              {live.testFiles > 0   && <span>Test: <span className="text-yellow-400">{live.testFiles}</span></span>}
              {live.indexedChunks > 0 && <span>Indexed: <span className="text-brand-400">{live.indexedChunks}</span></span>}
            </div>
          )}

          {/* Stages */}
          <div className="space-y-1.5 mb-4">
            {STAGES.map(stage => {
              const st = stageStatus(stage.key)
              return (
                <div key={stage.key} className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
                  st === 'done'    && 'bg-green-900/20',
                  st === 'active'  && 'bg-brand-900/30 border border-brand-800/50',
                  st === 'pending' && 'opacity-40',
                )}>
                  {st === 'done'    && <CheckCircle2 size={14} className="text-green-400 shrink-0" />}
                  {st === 'active'  && <Loader2 size={14} className="animate-spin text-brand-400 shrink-0" />}
                  {st === 'pending' && <Clock size={14} className="text-gray-600 shrink-0" />}
                  <span className={
                    st === 'done' ? 'text-green-300' :
                    st === 'active' ? 'text-brand-300' : 'text-gray-500'
                  }>
                    {stage.label}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Approach results live */}
          {Object.keys(live.approachResults).length > 0 && (
            <div className="border-t border-gray-800 pt-3">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Approach Results</div>

              {/* Conventional baselines */}
              <div className="text-[10px] text-gray-600 mb-1.5 pl-1 uppercase tracking-wider">
                Conventional Baselines
              </div>
              <div className="space-y-2 mb-3">
                {(['keyword', 'structural'] as const).map(approach => {
                  const res = live.approachResults[approach]
                  if (!res) return null
                  const statusCls = STATUS_COLOR[res.status ?? 'SUCCESS'] ?? 'text-gray-400'
                  return (
                    <div key={approach} className="bg-gray-800/40 rounded-lg p-2">
                      <div className="flex items-center gap-2 text-xs">
                        <CheckCircle2 size={11} className="text-green-400 shrink-0" />
                        <span className="text-gray-300 font-medium w-36">{APPROACH_LABELS[approach]}</span>
                        {res.error
                          ? <span className="text-red-400">{res.error.slice(0, 50)}</span>
                          : <>
                            <span className="text-green-400">{res.sourceCount} source</span>
                            {res.count > res.sourceCount && <span className="text-orange-400">+{res.count - res.sourceCount} evidence</span>}
                            {res.ms && <span className="text-gray-500">({res.ms.toFixed(0)}ms)</span>}
                            <span className={clsx('ml-auto font-mono', statusCls)}>{res.status}</span>
                          </>
                        }
                      </div>
                      {res.topFile && (
                        <div className="mt-1 pl-5 text-xs">
                          <span className="font-mono text-blue-400">{res.topFile.split('/').pop()}</span>
                          <span className="text-gray-600">::</span>
                          <span className="font-mono text-yellow-300">{res.topFunction}()</span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* AI approaches */}
              <div className="text-[10px] text-gray-600 mb-1.5 pl-1 uppercase tracking-wider">
                AI Approaches — primary comparison
              </div>
              <div className="space-y-2">
                {(['llm_only', 'rag_llm'] as const).map(approach => {
                  const res = live.approachResults[approach]
                  if (!res) return null
                  const aiColors: Record<string, string> = { llm_only: 'text-yellow-300', rag_llm: 'text-green-300' }
                  const statusCls = STATUS_COLOR[res.status ?? 'SUCCESS'] ?? 'text-gray-400'
                  return (
                    <div key={approach} className="bg-gray-800/40 rounded-lg p-2">
                      <div className="flex items-center gap-2 text-xs">
                        <CheckCircle2 size={11} className="text-green-400 shrink-0" />
                        <span className={clsx('font-medium w-36', aiColors[approach])}>{APPROACH_LABELS[approach]}</span>
                        {res.error
                          ? <span className="text-red-400">{res.error.slice(0, 50)}</span>
                          : <>
                            <span className="text-green-400">{res.sourceCount} source</span>
                            {res.count > res.sourceCount && <span className="text-orange-400">+{res.count - res.sourceCount} evidence</span>}
                            {res.ms && <span className="text-gray-500">({res.ms.toFixed(0)}ms)</span>}
                            <span className={clsx('ml-auto font-mono', statusCls)}>{res.status}</span>
                          </>
                        }
                      </div>
                      {res.topFile && (
                        <div className="mt-1 pl-5 text-xs">
                          <span className="font-mono text-blue-400">{res.topFile.split('/').pop()}</span>
                          <span className="text-gray-600">::</span>
                          <span className="font-mono text-yellow-300">{res.topFunction}()</span>
                        </div>
                      )}
                      {res.pipelineStages && res.pipelineStages.length > 0 && (
                        <div className="mt-1 pl-5 flex flex-wrap gap-1">
                          {(res.pipelineStages as string[]).slice(-3).map((s: string) => (
                            <span key={s} className="text-[9px] bg-gray-700 text-gray-500 px-1 rounded font-mono">✓ {s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Preliminary top prediction */}
          {live.partialPredictions.length > 0 && (
            <div className="border-t border-gray-800 pt-3 mt-3">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                Top Bug Location (preliminary — source file only)
              </div>
              <div className="bg-yellow-950/30 border border-yellow-900/40 rounded-lg p-3">
                <div className="font-mono text-sm text-blue-400">{live.partialPredictions[0].file}</div>
                <div className="font-mono text-sm text-yellow-300 mt-0.5">{live.partialPredictions[0].function}()</div>
                <div className="text-xs text-gray-500 mt-1">
                  Lines {live.partialPredictions[0].line_start}–{live.partialPredictions[0].line_end} ·
                  {' '}{live.partialPredictions[0].evidence_strength} confidence ·
                  {' '}source file
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="card border-red-900/50 flex items-start gap-3">
          <AlertCircle size={18} className="text-red-400 mt-0.5 shrink-0" />
          <div>
            <div className="font-medium text-red-300 mb-1">Analysis failed</div>
            {error.split('\n').map((line, i) => (
              <p key={i} className="text-sm text-red-400 leading-relaxed">{line}</p>
            ))}
          </div>
        </div>
      )}

      {/* ── Full results dashboard ────────────────────────────────── */}
      {result && !loading && (
        <Dashboard
          result={result}
          liveLLMStages={live.liveLLMStages}
          liveRAGStages={live.liveRAGStages}
          llmProcessing={false}
          ragProcessing={false}
        />
      )}
    </div>
  )
}
