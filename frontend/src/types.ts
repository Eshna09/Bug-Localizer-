// Shared TypeScript types — Phase 2

export interface PredictedLocation {
  rank: number
  file: string
  function: string
  class_name?: string
  line_start: number
  line_end: number
  reason: string
  evidence_strength: 'High' | 'Medium' | 'Low' | 'Insufficient'
  source_code?: string
  retrieved_chunks: string[]
  is_test_file: boolean
  candidate_type: 'primary' | 'supporting_evidence'
  confidence?: number
}

export interface RetrievedChunk {
  chunk_id: string
  file: string
  function: string
  class_name?: string
  line_start: number
  line_end: number
  similarity_score: number
  code_preview: string
}

export interface RepoStats {
  repo_url: string
  commit_hash: string
  detected_language: string
  total_files: number
  source_files: number
  test_files: number
  total_functions: number
  total_classes: number
  total_dependencies: number
  code_chunks: number
  indexed_chunks: number
  languages: Record<string, number>
}

export interface ResourceUsage {
  cpu_avg_percent: number | null
  cpu_peak_percent: number | null
  memory_rss_mb_start: number | null
  memory_rss_mb_peak: number | null
  memory_delta_mb: number | null
  gpu_utilization: string
  measurement_note: string
}

export interface RejectedPrediction {
  file: string
  function: string
  reason: string
  llm_line_start?: number
  llm_line_end?: number
}

export interface ApproachDetail {
  approach: string
  status: 'SUCCESS' | 'TIMEOUT' | 'API_ERROR' | 'PARSING_ERROR' | 'EMPTY_RESPONSE'
  latency_ms?: number
  top_prediction_file?: string
  top_prediction_function?: string
  top_prediction_rank?: number
  evidence_strength?: string
  top5_predictions: PredictedLocation[]
  supporting_evidence?: PredictedLocation[]
  retrieved_chunk_details: RetrievedChunk[]
  pipeline_stages: string[]
  context_size_chars?: number
  token_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
  model?: string
  embedding_model?: string
  num_source_predictions: number
  num_test_predictions: number
  top_file?: string
  top_function?: string
  error?: string
  message?: string
  resource_usage?: ResourceUsage
  rejected_predictions?: RejectedPrediction[]
}

export interface ApproachSummary {
  approach: string
  status?: string
  top_prediction_file?: string
  top_prediction_function?: string
  top_prediction_rank?: number
  evidence_strength?: string
  latency_ms?: number
  error?: string
}

export interface RootCause {
  file: string
  function: string
  line_start: number
  line_end: number
  explanation: string
}

export interface AffectedComponent {
  file: string
  function: string
  how_affected: string
}

export interface BugExplanation {
  what_is_wrong: string
  why_is_it_wrong: string
  what_should_happen: string
  what_actually_happens: string
  downstream_impact: string
  root_cause: RootCause
  affected_components: AffectedComponent[]
  dependency_chain: string[]
}

export interface ProposedFix {
  file: string
  function: string
  current_code: string
  proposed_code: string
  diff: string
  minimal_change_description: string
  why_this_fixes: string
  what_changed: string[]
  why_safe: string
  potential_side_effects: string
  is_minimal: boolean
}

export interface TestResult {
  name: string
  status: 'PASSED' | 'FAILED' | 'ERROR' | 'SKIPPED'
  output?: string
}

export interface VerificationResult {
  status: 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'NOT_VERIFIED' | 'VERIFICATION_UNAVAILABLE'
  reproduction_test_before?: string
  reproduction_test_after?: string
  tests_before: TestResult[]
  tests_after: TestResult[]
  passed_before: number
  failed_before: number
  passed_after: number
  failed_after: number
  notes: string
  docker_used: boolean
}

export interface AnalysisResult {
  analysis_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  repo_url: string
  commit_hash: string
  detected_language: string
  issue_description: string
  timestamp: string
  repo_stats?: RepoStats
  approach_summaries: ApproachSummary[]
  approach_details?: ApproachDetail[]
  primary_predictions: PredictedLocation[]
  keyword_predictions: PredictedLocation[]
  structural_predictions: PredictedLocation[]
  llm_only_predictions: PredictedLocation[]
  rag_llm_predictions: PredictedLocation[]
  rag_retrieved_chunks?: RetrievedChunk[]
  bug_explanation?: BugExplanation
  proposed_fix?: ProposedFix
  verification?: VerificationResult
  error?: string
}

export interface HistoryItem {
  id: string
  repo_url: string
  commit_hash?: string
  status: string
  timestamp?: string
  issue_description: string
  top_prediction?: string
  verification_status?: string
}
