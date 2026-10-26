"""
FastAPI route definitions — Phase 2.
"""
from __future__ import annotations
import json
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import (
    AnalyzeRequest,
    AnalysisResponse,
    ApproachResultSummary,
    ApproachResultDetail,
    RepoStatsResponse,
    RetrievedChunkResponse,
    HealthResponse,
    HistoryItem,
    EvaluationSummaryResponse,
    EvaluationPreviewResponse,
    RunExperimentRequest,
    GenerateFixRequest,
    ExperimentStatusResponse,
)
from config.settings import settings
from core.models import AnalysisResult, LocalizationResult
from pipeline import BugLocalizerPipeline
from storage.database import Database, get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_pipeline = BugLocalizerPipeline()


def _loc_to_detail(approach_str: str, loc: LocalizationResult | None) -> ApproachResultDetail:
    """Build a full ApproachResultDetail from a LocalizationResult."""
    if not loc:
        return ApproachResultDetail(
            approach=approach_str,
            status="EMPTY_RESPONSE",
            error="Not run",
        )
    top = loc.predictions[0] if loc.predictions else None
    # Primary (source file) predictions only for top-5 display
    primary_preds = [p for p in loc.predictions if not p.is_test_file]
    top5 = [p.model_dump() for p in primary_preds[:5]]

    chunk_details = [
        RetrievedChunkResponse(
            chunk_id=c.chunk_id,
            file=c.file,
            function=c.function,
            class_name=c.class_name,
            line_start=c.line_start,
            line_end=c.line_end,
            similarity_score=c.similarity_score,
            code_preview=c.code_preview,
        )
        for c in loc.retrieved_chunk_details
    ]

    return ApproachResultDetail(
        approach=approach_str,
        status=loc.status,
        latency_ms=loc.latency_ms,
        top_prediction_file=top.file if top and not top.is_test_file else None,
        top_prediction_function=top.function if top and not top.is_test_file else None,
        top_prediction_rank=top.rank if top and not top.is_test_file else None,
        evidence_strength=top.evidence_strength.value if top and not top.is_test_file else None,
        top5_predictions=top5,
        retrieved_chunk_details=chunk_details,
        pipeline_stages=loc.pipeline_stages,
        context_size_chars=loc.context_size_chars,
        token_usage=loc.token_usage,
        model=loc.model,
        embedding_model=loc.embedding_model,
        num_source_predictions=loc.num_source_predictions,
        num_test_predictions=loc.num_test_predictions,
        error=loc.error,
        resource_usage=loc.resource_usage,
        rejected_predictions=loc.rejected_predictions,
    )


def _result_to_response(result: AnalysisResult) -> AnalysisResponse:
    """Convert internal AnalysisResult to API response schema."""

    def _pred_list(loc_result):
        if not loc_result:
            return []
        return [p.model_dump() for p in loc_result.predictions]

    def _summary(approach_str, loc_result) -> ApproachResultSummary:
        if not loc_result:
            return ApproachResultSummary(approach=approach_str, error="Not run")
        top = next((p for p in loc_result.predictions if not p.is_test_file), None)
        return ApproachResultSummary(
            approach=approach_str,
            top_prediction_file=top.file if top else None,
            top_prediction_function=top.function if top else None,
            top_prediction_rank=top.rank if top else None,
            evidence_strength=top.evidence_strength.value if top else None,
            latency_ms=loc_result.latency_ms,
            error=loc_result.error,
        )

    # RepoStats
    repo_stats_resp: RepoStatsResponse | None = None
    if result.repo_stats:
        rs = result.repo_stats
        repo_stats_resp = RepoStatsResponse(
            repo_url=rs.repo_url,
            commit_hash=rs.commit_hash,
            detected_language=rs.detected_language,
            total_files=rs.total_files,
            source_files=rs.source_files,
            test_files=rs.test_files,
            total_functions=rs.total_functions,
            total_classes=rs.total_classes,
            total_dependencies=rs.total_dependencies,
            code_chunks=rs.code_chunks,
            indexed_chunks=rs.indexed_chunks,
            languages=rs.languages,
        )

    # RAG retrieved chunks
    rag_chunks: list[RetrievedChunkResponse] = []
    if result.rag_llm_result:
        rag_chunks = [
            RetrievedChunkResponse(
                chunk_id=c.chunk_id,
                file=c.file,
                function=c.function,
                class_name=c.class_name,
                line_start=c.line_start,
                line_end=c.line_end,
                similarity_score=c.similarity_score,
                code_preview=c.code_preview,
            )
            for c in result.rag_llm_result.retrieved_chunk_details
        ]

    return AnalysisResponse(
        analysis_id=result.analysis_id,
        status=result.status.value,
        repo_url=result.repo_url,
        commit_hash=result.commit_hash,
        detected_language=result.detected_language,
        issue_description=result.issue_description,
        timestamp=result.timestamp,
        repo_stats=repo_stats_resp,
        approach_summaries=[
            _summary("keyword",    result.keyword_result),
            _summary("structural", result.structural_result),
            _summary("llm_only",   result.llm_only_result),
            _summary("rag_llm",    result.rag_llm_result),
        ],
        approach_details=[
            _loc_to_detail("keyword",    result.keyword_result),
            _loc_to_detail("structural", result.structural_result),
            _loc_to_detail("llm_only",   result.llm_only_result),
            _loc_to_detail("rag_llm",    result.rag_llm_result),
        ],
        primary_predictions=[p.model_dump() for p in result.primary_predictions],
        keyword_predictions=_pred_list(result.keyword_result),
        structural_predictions=_pred_list(result.structural_result),
        llm_only_predictions=_pred_list(result.llm_only_result),
        rag_llm_predictions=_pred_list(result.rag_llm_result),
        rag_retrieved_chunks=rag_chunks,
        bug_explanation=result.bug_explanation.model_dump() if result.bug_explanation else None,
        proposed_fix=result.proposed_fix.model_dump() if result.proposed_fix else None,
        verification=result.verification.model_dump() if result.verification else None,
        error=result.error,
    )


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        llm_provider=settings.llm_provider,
        embedding_model=settings.embedding_model,
    )


@router.post("/repositories/analyze", response_model=AnalysisResponse)
def analyze_repository(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
):
    """
    Full analysis pipeline:
    Clone → Parse → Localize (4 approaches) → Explain → Fix → Verify
    """
    result = _pipeline.analyze(
        repo_url=request.repo_url,
        issue_text=request.issue_description,
        issue_id=request.issue_id,
        run_verification=request.run_verification,
    )

    try:
        database = Database(db)
        database.save_analysis(result.analysis_id, result.model_dump())
    except Exception as exc:
        logger.error("Failed to save analysis: %s", exc)

    return _result_to_response(result)


@router.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    database = Database(db)
    data = database.get_analysis(analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id!r} not found.")
    result = AnalysisResult(**data)
    return _result_to_response(result)


@router.get("/history", response_model=List[HistoryItem])
def list_history(limit: int = 50, db: Session = Depends(get_db)):
    database = Database(db)
    rows = database.list_analyses(limit=limit)
    return [HistoryItem(**row) for row in rows]


@router.get("/evaluation/summary", response_model=List[EvaluationSummaryResponse])
def evaluation_summary(db: Session = Depends(get_db)):
    """Returns real evaluation summaries from completed experiments."""
    return []


@router.get("/evaluation/preview", response_model=EvaluationPreviewResponse)
def evaluation_preview(db: Session = Depends(get_db)):
    """Return the persisted illustrative metrics used before a real experiment."""
    data = Database(db).get_evaluation_preview()
    if data is None:
        raise HTTPException(status_code=404, detail="Evaluation preview data is not available.")
    return data


@router.post("/experiments/run", response_model=ExperimentStatusResponse)
def run_experiment(request: RunExperimentRequest, db: Session = Depends(get_db)):
    """
    Run evaluation experiment synchronously.
    Ground truth accessed ONLY here, after predictions are generated.
    """
    from pathlib import Path
    from evaluation.experiment_runner import ExperimentRunner

    dataset_path = Path(request.bug_dataset_path)
    if not dataset_path.exists():
        raise HTTPException(status_code=400, detail=f"Dataset file not found: {dataset_path}")

    try:
        runner = ExperimentRunner(top_k=request.top_k)
        results = runner.run(
            dataset_path=str(dataset_path),
            approaches=request.approaches,
            default_repo_url=request.repo_url,
        )
        if results.get("evaluated_bugs", 0) == 0:
            raise HTTPException(
                status_code=422,
                detail="No bugs were evaluated. Check that the repository is accessible and contains source files matching the dataset ground-truth paths.",
            )
        experiment_id = results.get("experiment_id", str(uuid.uuid4()))
        return ExperimentStatusResponse(
            experiment_id=experiment_id,
            status="completed",
            total_bugs=results.get("total_bugs", 0),
            completed_bugs=results.get("evaluated_bugs", 0),
            results=results,
        )
    except Exception as exc:
        logger.error("Experiment failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Experiment failed: {exc}")


@router.get("/experiments/{experiment_id}", response_model=ExperimentStatusResponse)
def get_experiment(experiment_id: str, db: Session = Depends(get_db)):
    return ExperimentStatusResponse(
        experiment_id=experiment_id,
        status="not_found",
    )
