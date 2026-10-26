import axios from 'axios'
import type {
  AnalysisResult, HistoryItem, PredictedLocation,
  BugExplanation, ProposedFix, RetrievedChunk,
} from '../types'

const api = axios.create({ baseURL: '/api', timeout: 900_000 })

// Direct backend URL — bypasses Vite proxy for long-running requests
const BACKEND = 'http://localhost:8000'

export interface AnalyzeRequest {
  repo_url: string
  issue_description: string
  issue_id?: string
  run_verification?: boolean
}

export interface EvaluationPreview {
  summaries: Array<{
    approach: string
    total_bugs: number
    [metric: string]: string | number | null
  }>
  breakdowns: Record<string, Record<string, Record<string, {
    top1_accuracy: number
    total_bugs: number
  }>>>
}

export interface ProgressEvent {
  type: 'started' | 'progress' | 'approach_done' | 'repo_stats' | 'predictions_ready' |
        'explanation_done' | 'fix_done' | 'completed' | 'error'
  stage?: string
  message?: string
  approach?: string
  status?: string
  predictions?: PredictedLocation[]
  top5_predictions?: PredictedLocation[]
  supporting_evidence?: PredictedLocation[]
  primary_predictions?: PredictedLocation[]
  pipeline_stages?: string[]
  chunk_details?: RetrievedChunk[]
  bug_explanation?: BugExplanation
  proposed_fix?: ProposedFix
  latency_ms?: number
  commit_hash?: string
  detected_language?: string
  total_functions?: number
  total_files?: number
  source_files?: number
  test_files?: number
  indexed_chunks?: number
  analysis_id?: string
  result?: AnalysisResult
  error?: string
  pipeline?: string[]
  embedding_model?: string
  embedding_backend?: string
  top_file?: string
  top_function?: string
  top_lines?: string
  num_source_predictions?: number
  num_test_predictions?: number
  context_size_chars?: number
  token_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
  model?: string
  [key: string]: any
}

/**
 * analyzeRepositoryStream — uses the synchronous REST endpoint instead of SSE.
 *
 * Why: The SSE stream works on the backend but the browser/Vite proxy kills the
 * connection after ~60s. The REST endpoint does exactly the same pipeline and
 * returns the full result when complete. We simulate progress events so the
 * existing UI still works.
 */
export function analyzeRepositoryStream(
  req: AnalyzeRequest,
  onProgress: (event: ProgressEvent) => void,
): Promise<AnalysisResult> {
  // Emit fake started + progress events so the UI shows activity
  onProgress({ type: 'started', stage: 'cloning', message: 'Cloning repository...' })

  // After 3s emit parsing
  const t1 = setTimeout(() => {
    onProgress({ type: 'progress', stage: 'parsing', message: 'Parsing source files...' })
  }, 3000)

  // After 10s emit embedding
  const t2 = setTimeout(() => {
    onProgress({ type: 'progress', stage: 'embedding', message: 'Building semantic index...' })
  }, 10000)

  // After 30s emit llm_only
  const t3 = setTimeout(() => {
    onProgress({ type: 'progress', stage: 'llm_only', message: 'LLM-only localization running...' })
  }, 30000)

  // After 80s emit rag_llm
  const t4 = setTimeout(() => {
    onProgress({ type: 'progress', stage: 'rag_llm', message: 'RAG + LLM running...' })
  }, 80000)

  // After 140s emit explanation
  const t5 = setTimeout(() => {
    onProgress({ type: 'progress', stage: 'explanation', message: 'Generating explanation...' })
  }, 140000)

  // After 170s emit fix
  const t6 = setTimeout(() => {
    onProgress({ type: 'progress', stage: 'fix', message: 'Generating fix...' })
  }, 170000)

  function clearTimers() {
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3)
    clearTimeout(t4); clearTimeout(t5); clearTimeout(t6)
  }

  return fetch(`${BACKEND}/api/repositories/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
    .then(async res => {
      clearTimers()
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const result: AnalysisResult = await res.json()

      // Emit approach_done events from the returned data so the UI cards populate
      if (result.approach_details) {
        for (const d of result.approach_details) {
          onProgress({
            type: 'approach_done',
            approach: d.approach,
            status: d.status,
            predictions: d.top5_predictions ?? [],
            top5_predictions: d.top5_predictions ?? [],
            supporting_evidence: d.supporting_evidence ?? [],
            latency_ms: d.latency_ms,
            pipeline_stages: d.pipeline_stages ?? [],
            chunk_details: d.retrieved_chunk_details ?? [],
            context_size_chars: d.context_size_chars,
            token_usage: d.token_usage,
            model: d.model,
            embedding_model: d.embedding_model,
            num_source_predictions: d.num_source_predictions ?? 0,
            num_test_predictions: d.num_test_predictions ?? 0,
            top_file: d.top_prediction_file,
            top_function: d.top_prediction_function,
            error: d.error,
            message: `${d.approach}: ${d.num_source_predictions ?? 0} source predictions`,
          })
        }
      }

      // Emit repo_stats
      if (result.repo_stats) {
        onProgress({ type: 'repo_stats', ...result.repo_stats } as any)
      }

      // Emit predictions_ready
      if (result.primary_predictions?.length) {
        onProgress({
          type: 'predictions_ready',
          primary_predictions: result.primary_predictions,
          top_file: result.primary_predictions[0]?.file,
          top_function: result.primary_predictions[0]?.function,
        })
      }

      // Emit explanation_done
      if (result.bug_explanation) {
        onProgress({ type: 'explanation_done', bug_explanation: result.bug_explanation })
      }

      // Emit fix_done
      if (result.proposed_fix) {
        onProgress({ type: 'fix_done', proposed_fix: result.proposed_fix })
      }

      return result
    })
    .catch(err => {
      clearTimers()
      throw err
    })
}

export async function analyzeRepository(req: AnalyzeRequest): Promise<AnalysisResult> {
  const { data } = await api.post<AnalysisResult>('/repositories/analyze', req)
  return data
}

export async function getAnalysis(id: string): Promise<AnalysisResult> {
  const { data } = await api.get<AnalysisResult>(`/analysis/${id}`)
  return data
}

export async function listHistory(limit = 50): Promise<HistoryItem[]> {
  const { data } = await api.get<HistoryItem[]>('/history', { params: { limit } })
  return data
}

export async function checkHealth() {
  const { data } = await api.get('/health')
  return data
}

export async function getEvaluationPreview(): Promise<EvaluationPreview> {
  const { data } = await api.get<EvaluationPreview>('/evaluation/preview')
  return data
}

export async function runExperiment(payload: {
  bug_dataset_path: string
  repo_url: string
  approaches: string[]
  top_k?: number
}) {
  // Long timeout — each bug takes ~3 min with local LLM, 5 bugs = ~15 min
  const { data } = await axios.create({ baseURL: 'http://localhost:8000', timeout: 1800_000 })
    .post('/api/experiments/run', payload)
  return data
}
