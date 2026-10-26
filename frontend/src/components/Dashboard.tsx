import type { AnalysisResult } from '../types'
import ErrorBoundary from './ErrorBoundary'
import RepoStatsPanel from './panels/RepoStatsPanel'
import ApproachComparisonPanel from './panels/ApproachComparisonPanel'
import LLMvsRAGPanel from './panels/LLMvsRAGPanel'
import SameQueryComparisonPanel from './panels/SameQueryComparisonPanel'
import RAGEvidencePanel from './panels/RAGEvidencePanel'
import Top5RankingPanel from './panels/Top5RankingPanel'
import RootCausePanel from './panels/RootCausePanel'
import ProposedFixPanel from './panels/ProposedFixPanel'
import VerificationPanel from './panels/VerificationPanel'
import IssueSummaryCard from './cards/IssueSummaryCard'

interface Props {
  result: AnalysisResult
  liveLLMStages?: string[]
  liveRAGStages?: string[]
  llmProcessing?: boolean
  ragProcessing?: boolean
}

export default function Dashboard({
  result,
  liveLLMStages,
  liveRAGStages,
  llmProcessing = false,
  ragProcessing  = false,
}: Props) {
  if (!result) return null

  const hasLLM = (result.llm_only_predictions?.length ?? 0) > 0 ||
    result.approach_details?.some(d => d.approach === 'llm_only')
  const hasRAG = (result.rag_llm_predictions?.length ?? 0) > 0 ||
    result.approach_details?.some(d => d.approach === 'rag_llm')
  const hasRAGChunks = (result.rag_retrieved_chunks?.length ?? 0) > 0

  return (
    <div className="space-y-6">

      {/* 1. Issue + Repository */}
      <ErrorBoundary label="Issue Summary">
        <IssueSummaryCard result={result} />
      </ErrorBoundary>

      {/* 2. Repository Statistics */}
      {result.repo_stats && (
        <ErrorBoundary label="Repo Stats">
          <RepoStatsPanel stats={result.repo_stats} />
        </ErrorBoundary>
      )}

      {/* 3. Four Approach Comparison */}
      <ErrorBoundary label="Approach Comparison">
        <ApproachComparisonPanel result={result} />
      </ErrorBoundary>

      {/* 4. LLM Only vs RAG + LLM */}
      {(hasLLM || hasRAG) && (
        <ErrorBoundary label="LLM vs RAG Panel">
          <LLMvsRAGPanel
            result={result}
            liveLLMStages={liveLLMStages}
            liveRAGStages={liveRAGStages}
            llmProcessing={llmProcessing}
            ragProcessing={ragProcessing}
          />
        </ErrorBoundary>
      )}

      {/* 4b. Same-query metric comparison */}
      {(hasLLM || hasRAG) && (
        <ErrorBoundary label="Same Query Comparison">
          <SameQueryComparisonPanel result={result} />
        </ErrorBoundary>
      )}

      {/* 5. RAG Retrieved Evidence */}
      {hasRAGChunks && (
        <ErrorBoundary label="RAG Evidence">
          <RAGEvidencePanel chunks={result.rag_retrieved_chunks!} />
        </ErrorBoundary>
      )}

      {/* 6. Top-5 Final Ranking */}
      <ErrorBoundary label="Top-5 Ranking">
        <Top5RankingPanel result={result} />
      </ErrorBoundary>

      {/* 7. Root Cause Analysis */}
      {result.bug_explanation && (
        <ErrorBoundary label="Root Cause">
          <RootCausePanel explanation={result.bug_explanation} result={result} />
        </ErrorBoundary>
      )}

      {/* 8. Fix Proposal */}
      {result.proposed_fix && (
        <ErrorBoundary label="Proposed Fix">
          <ProposedFixPanel fix={result.proposed_fix} />
        </ErrorBoundary>
      )}

      {/* 9. Verification */}
      {result.verification && (
        <ErrorBoundary label="Verification">
          <VerificationPanel verification={result.verification} />
        </ErrorBoundary>
      )}

    </div>
  )
}
