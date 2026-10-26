"""
Pydantic request/response schemas for the REST API — Phase 2.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL (https://github.com/...)")
    issue_description: str = Field(..., description="Natural-language bug report")
    issue_id: Optional[str] = Field(None, description="Optional issue identifier for tracking")
    run_verification: bool = Field(False, description="Whether to run Docker-based fix verification")
    rag_top_k: Optional[int] = Field(None, description="Override RAG top-K retrieval count")


class LocalizeRequest(BaseModel):
    repo_url: str
    issue_description: str
    issue_id: Optional[str] = None
    approaches: List[str] = Field(
        default=["keyword", "structural", "llm_only", "rag_llm"],
    )
    top_k: int = 5


class GenerateFixRequest(BaseModel):
    analysis_id: str
    run_verification: bool = True


class RunExperimentRequest(BaseModel):
    bug_dataset_path: str = Field(..., description="Path to ground-truth bug dataset JSON")
    repo_url: str
    approaches: List[str] = Field(default=["keyword", "structural", "llm_only", "rag_llm"])
    top_k: int = 5
    experiment_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Shared sub-schemas
# ---------------------------------------------------------------------------

class RepoStatsResponse(BaseModel):
    """Repository statistics from the actual analysis."""
    repo_url: str
    commit_hash: str
    detected_language: str
    total_files: int = 0
    source_files: int = 0
    test_files: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_dependencies: int = 0
    code_chunks: int = 0
    indexed_chunks: int = 0
    languages: Dict[str, int] = Field(default_factory=dict)


class RetrievedChunkResponse(BaseModel):
    """A retrieved code chunk with its similarity score — for RAG evidence panel."""
    chunk_id: str
    file: str
    function: str
    class_name: Optional[str] = None
    line_start: int
    line_end: int
    similarity_score: float
    code_preview: str


class ApproachResultDetail(BaseModel):
    """Full detail for one localization approach — for approach comparison cards."""
    approach: str
    status: str                      # SUCCESS | TIMEOUT | API_ERROR | PARSING_ERROR | EMPTY_RESPONSE
    latency_ms: Optional[float] = None
    top_prediction_file: Optional[str] = None
    top_prediction_function: Optional[str] = None
    top_prediction_rank: Optional[int] = None
    evidence_strength: Optional[str] = None
    top5_predictions: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_chunk_details: List[RetrievedChunkResponse] = Field(default_factory=list)
    pipeline_stages: List[str] = Field(default_factory=list)
    context_size_chars: Optional[int] = None
    token_usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    embedding_model: Optional[str] = None
    num_source_predictions: int = 0
    num_test_predictions: int = 0
    error: Optional[str] = None
    # Phase 3 additions
    resource_usage: Optional[Dict[str, Any]] = None
    rejected_predictions: List[Dict[str, Any]] = Field(default_factory=list)


# Keep the old summary format for backward compatibility
class ApproachResultSummary(BaseModel):
    approach: str
    top_prediction_file: Optional[str] = None
    top_prediction_function: Optional[str] = None
    top_prediction_rank: Optional[int] = None
    evidence_strength: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    llm_provider: str
    embedding_model: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    repo_url: str
    commit_hash: str
    detected_language: str
    issue_description: str
    timestamp: str

    # Repository statistics
    repo_stats: Optional[RepoStatsResponse] = None

    # Approach summaries (backward-compat)
    approach_summaries: List[ApproachResultSummary] = Field(default_factory=list)

    # Full approach details with top-5, chunk details, pipeline stages
    approach_details: List[ApproachResultDetail] = Field(default_factory=list)

    # Full prediction lists per approach
    primary_predictions: List[Dict[str, Any]] = Field(default_factory=list)
    keyword_predictions: List[Dict[str, Any]] = Field(default_factory=list)
    structural_predictions: List[Dict[str, Any]] = Field(default_factory=list)
    llm_only_predictions: List[Dict[str, Any]] = Field(default_factory=list)
    rag_llm_predictions: List[Dict[str, Any]] = Field(default_factory=list)

    # Retrieved chunks for RAG evidence panel
    rag_retrieved_chunks: List[RetrievedChunkResponse] = Field(default_factory=list)

    bug_explanation: Optional[Dict[str, Any]] = None
    proposed_fix: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None

    error: Optional[str] = None


class HistoryItem(BaseModel):
    id: str
    repo_url: str
    commit_hash: Optional[str] = None
    status: str
    timestamp: Optional[str] = None
    issue_description: str
    top_prediction: Optional[str] = None
    verification_status: Optional[str] = None


class EvaluationSummaryResponse(BaseModel):
    approach: str
    total_bugs: int
    top1_accuracy: float
    top3_accuracy: float
    top5_accuracy: float
    mrr: float
    file_level_top1: float
    avg_latency_ms: Optional[float] = None
    avg_tokens: Optional[int] = None


class EvaluationPreviewResponse(BaseModel):
    summaries: List[Dict[str, Any]]
    breakdowns: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]


class ExperimentStatusResponse(BaseModel):
    experiment_id: str
    status: str          # queued | running | completed | failed
    total_bugs: int = 0
    completed_bugs: int = 0
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
