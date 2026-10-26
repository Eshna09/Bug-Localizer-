"""
Shared data models used throughout the pipeline.
These are Pydantic models — not database models.
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class LocalizationApproach(str, Enum):
    KEYWORD = "keyword"
    STRUCTURAL = "structural"
    LLM_ONLY = "llm_only"
    RAG_LLM = "rag_llm"


class EvidenceStrength(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INSUFFICIENT = "Insufficient"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Repository & Parsing
# ---------------------------------------------------------------------------

class FunctionUnit(BaseModel):
    """A single parsed function/method from source code."""
    file_path: str
    class_name: Optional[str] = None
    function_name: str
    start_line: int
    end_line: int
    source_code: str
    imports: List[str] = Field(default_factory=list)
    calls: List[str] = Field(default_factory=list)       # functions this calls
    called_by: List[str] = Field(default_factory=list)   # functions that call this

    @property
    def qualified_name(self) -> str:
        if self.class_name:
            return f"{self.class_name}.{self.function_name}"
        return self.function_name

    @property
    def chunk_id(self) -> str:
        return f"{self.file_path}::{self.qualified_name}::{self.start_line}"


class RepositoryIndex(BaseModel):
    """Parsed and indexed representation of a cloned repository."""
    repo_url: str
    local_path: str
    commit_hash: str
    detected_language: str
    total_files: int
    total_functions: int
    functions: List[FunctionUnit] = Field(default_factory=list)
    file_tree: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------

class PredictedLocation(BaseModel):
    """A single ranked bug location prediction."""
    rank: int
    file: str
    function: str
    class_name: Optional[str] = None
    line_start: int
    line_end: int
    reason: str
    evidence_strength: EvidenceStrength = EvidenceStrength.LOW
    source_code: Optional[str] = None
    retrieved_chunks: List[str] = Field(default_factory=list)
    # Phase 2 additions
    is_test_file: bool = False
    candidate_type: str = "primary"   # "primary" | "supporting_evidence"
    confidence: Optional[float] = None


class RetrievedChunkDetail(BaseModel):
    """A single retrieved code chunk with its similarity score (for RAG visibility)."""
    chunk_id: str
    file: str
    function: str
    class_name: Optional[str] = None
    line_start: int
    line_end: int
    similarity_score: float
    code_preview: str  # first ~300 chars of source


class LocalizationResult(BaseModel):
    """Output from a single localization approach."""
    approach: LocalizationApproach
    issue_id: str
    repository: str
    commit_hash: str
    predictions: List[PredictedLocation] = Field(default_factory=list)
    retrieved_chunks: List[str] = Field(default_factory=list)
    retrieved_chunk_details: List[RetrievedChunkDetail] = Field(default_factory=list)
    model: Optional[str] = None
    embedding_model: Optional[str] = None
    prompt_version: Optional[str] = None
    latency_ms: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None
    # Phase 2: explicit status for UI display
    status: str = "SUCCESS"   # SUCCESS | TIMEOUT | API_ERROR | PARSING_ERROR | EMPTY_RESPONSE
    pipeline_stages: List[str] = Field(default_factory=list)  # stages completed
    context_size_chars: Optional[int] = None   # chars sent to LLM
    num_source_predictions: int = 0
    num_test_predictions: int = 0
    # Phase 3: resource monitoring (populated by resource_monitor.run_with_resources)
    resource_usage: Optional[Dict[str, Any]] = None
    # Phase 3: hallucination / rejection tracking
    rejected_predictions: List[Dict[str, Any]] = Field(default_factory=list)


class RepoStats(BaseModel):
    """Repository-level statistics collected during parsing."""
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


# ---------------------------------------------------------------------------
# Bug Explanation
# ---------------------------------------------------------------------------

class RootCause(BaseModel):
    file: str
    function: str
    line_start: int
    line_end: int
    explanation: str


class AffectedComponent(BaseModel):
    file: str
    function: str
    how_affected: str


class BugExplanation(BaseModel):
    what_is_wrong: str
    why_is_it_wrong: str
    what_should_happen: str
    what_actually_happens: str
    downstream_impact: str
    root_cause: RootCause
    affected_components: List[AffectedComponent] = Field(default_factory=list)
    dependency_chain: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Fix Generation
# ---------------------------------------------------------------------------

class ProposedFix(BaseModel):
    file: str
    function: str
    current_code: str
    proposed_code: str
    diff: str
    minimal_change_description: str
    why_this_fixes: str
    what_changed: List[str] = Field(default_factory=list)
    why_safe: str
    potential_side_effects: str
    is_minimal: bool = True


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class TestResult(BaseModel):
    name: str
    status: str   # "PASSED" | "FAILED" | "ERROR" | "SKIPPED"
    output: Optional[str] = None


class VerificationResult(BaseModel):
    status: VerificationStatus
    reproduction_test_before: Optional[str] = None   # "PASSED" | "FAILED" | "N/A"
    reproduction_test_after: Optional[str] = None
    tests_before: List[TestResult] = Field(default_factory=list)
    tests_after: List[TestResult] = Field(default_factory=list)
    passed_before: int = 0
    failed_before: int = 0
    passed_after: int = 0
    failed_after: int = 0
    notes: str = ""
    docker_used: bool = False


# ---------------------------------------------------------------------------
# Complete Analysis Result
# ---------------------------------------------------------------------------

class AnalysisResult(BaseModel):
    """The complete result of one bug analysis."""
    analysis_id: str
    status: AnalysisStatus
    repo_url: str
    commit_hash: str
    detected_language: str
    issue_description: str

    # Localization
    keyword_result: Optional[LocalizationResult] = None
    structural_result: Optional[LocalizationResult] = None
    llm_only_result: Optional[LocalizationResult] = None
    rag_llm_result: Optional[LocalizationResult] = None

    # Primary results ranked by agreement across localization approaches
    primary_predictions: List[PredictedLocation] = Field(default_factory=list)

    # Explanation and fix (derived from primary localization — AFTER prediction is recorded)
    bug_explanation: Optional[BugExplanation] = None
    proposed_fix: Optional[ProposedFix] = None
    verification: Optional[VerificationResult] = None

    # Phase 2: Repository statistics
    repo_stats: Optional[RepoStats] = None

    # Metadata
    timestamp: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class EvaluationRecord(BaseModel):
    bug_id: str
    ground_truth_file: str
    ground_truth_function: str
    approach: LocalizationApproach
    predictions: List[PredictedLocation]
    category: str = ""
    difficulty: str = ""
    issue_quality: str = ""
    scope: str = ""
    issue_type: str = ""
    top1_correct: bool = False
    top3_correct: bool = False
    top5_correct: bool = False
    reciprocal_rank: float = 0.0
    file_level_top1: bool = False
    retrieval_hit: Optional[bool] = None
    rejected_prediction_count: int = 0
    latency_ms: Optional[float] = None
    token_count: Optional[int] = None
    cpu_avg_percent: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    test_passed: Optional[bool] = None


class EvaluationSummary(BaseModel):
    approach: LocalizationApproach
    total_bugs: int
    top1_accuracy: float
    top3_accuracy: float
    top5_accuracy: float
    mrr: float
    file_level_top1: float
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    retrieval_recall_at_k: Optional[float] = None
    hallucination_rate: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    avg_tokens: Optional[float] = None
    avg_cpu_percent: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    test_pass_rate: Optional[float] = None
    records: List[EvaluationRecord] = Field(default_factory=list)
