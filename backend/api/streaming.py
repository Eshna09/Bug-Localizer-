"""
Streaming analysis endpoint using Server-Sent Events (SSE) — Phase 2.

SSE event types emitted:
  started           → analysis_id, timestamp
  progress          → stage, message, [metadata]
  approach_done     → approach, status, predictions, latency_ms, pipeline_stages, chunk_details
  repo_stats        → full RepoStats object
  predictions_ready → primary_predictions, top_file, top_function
  explanation_done  → bug_explanation
  fix_done          → proposed_fix
  completed         → full result object
  error             → stage, message

Keepalive ": ping" comments are sent every 10 s during LLM/embedding calls.
"""
from __future__ import annotations
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.ingestion import clone_repository, scan_source_files, _detect_language
from core.models import RepoStats
from core.parser import MultiFileParser
from localization import (
    KeywordSearchLocalizer,
    StructuralAnalysisLocalizer,
    LLMOnlyLocalizer,
    RAGLLMLocalizer,
)
from localization.embeddings import CodeVectorStore
from localization.file_classifier import is_test_file, is_source_file
from explanation import BugExplainer
from fix import FixGenerator
from config.settings import settings

logger = logging.getLogger(__name__)
stream_router = APIRouter()

_llm_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm_worker")

_keyword_localizer    = KeywordSearchLocalizer()
_structural_localizer = StructuralAnalysisLocalizer()
_llm_only_localizer   = LLMOnlyLocalizer()
_explainer            = BugExplainer()
_fix_generator        = FixGenerator()


class StreamRequest(BaseModel):
    repo_url: str
    issue_description: str
    run_verification: bool = False


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _ping() -> str:
    return ": ping\n\n"


async def _run_in_thread(fn, *args, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


async def _run_llm_with_keepalive(fn, *args, ping_interval: int = 10, **kwargs):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_llm_executor, lambda: fn(*args, **kwargs))

    async def pings():
        while not future.done():
            yield _ping()
            await asyncio.sleep(ping_interval)

    return future, pings()


def _build_repo_stats_dict(
    repo_url: str, commit_hash: str, language: str,
    source_files: list, functions: list, indexed_chunks: int,
) -> dict:
    source_count = sum(1 for f in source_files if is_source_file(str(f)))
    test_count   = sum(1 for f in source_files if is_test_file(str(f)))
    class_names  = {u.class_name for u in functions if u.class_name}
    all_deps: set = set()
    for u in functions:
        all_deps.update(u.calls)
    lang_counts: dict = {}
    for f in source_files:
        ext = Path(str(f)).suffix.lower()
        lang_counts[ext] = lang_counts.get(ext, 0) + 1
    return {
        "repo_url": repo_url,
        "commit_hash": commit_hash,
        "detected_language": language,
        "total_files": len(source_files),
        "source_files": source_count,
        "test_files": test_count,
        "total_functions": len(functions),
        "total_classes": len(class_names),
        "total_dependencies": len(all_deps),
        "code_chunks": len(functions),
        "indexed_chunks": indexed_chunks,
        "languages": lang_counts,
    }


def _approach_done_payload(approach: str, loc_result) -> dict:
    """Build an approach_done SSE payload with full detail."""
    if not loc_result:
        return {
            "approach": approach,
            "status": "EMPTY_RESPONSE",
            "predictions": [],
            "top5_predictions": [],
            "latency_ms": None,
            "pipeline_stages": [],
            "chunk_details": [],
            "num_source_predictions": 0,
            "num_test_predictions": 0,
            "error": "Not run",
        }

    all_preds  = [p.model_dump() for p in loc_result.predictions]
    primary    = [p.model_dump() for p in loc_result.predictions if not p.is_test_file]
    supporting = [p.model_dump() for p in loc_result.predictions if p.is_test_file]

    chunk_details = [
        {
            "chunk_id": c.chunk_id,
            "file": c.file,
            "function": c.function,
            "class_name": c.class_name,
            "line_start": c.line_start,
            "line_end": c.line_end,
            "similarity_score": c.similarity_score,
            "code_preview": c.code_preview,
        }
        for c in loc_result.retrieved_chunk_details
    ]

    top = next((p for p in loc_result.predictions if not p.is_test_file), None)

    return {
        "approach": approach,
        "status": loc_result.status,
        "predictions": all_preds,
        "top5_predictions": primary[:5],
        "supporting_evidence": supporting[:3],
        "latency_ms": loc_result.latency_ms,
        "pipeline_stages": loc_result.pipeline_stages,
        "chunk_details": chunk_details,
        "context_size_chars": loc_result.context_size_chars,
        "token_usage": loc_result.token_usage,
        "resource_usage": loc_result.resource_usage,
        "model": loc_result.model,
        "embedding_model": loc_result.embedding_model,
        "num_source_predictions": loc_result.num_source_predictions,
        "num_test_predictions": loc_result.num_test_predictions,
        "top_file": top.file if top else None,
        "top_function": top.function if top else None,
        "message": (
            f"{approach.replace('_', ' ').title()}: "
            f"{loc_result.num_source_predictions} source predictions "
            f"({loc_result.latency_ms:.0f}ms) [{loc_result.status}]"
            if loc_result else "Not run"
        ),
        "error": loc_result.error,
        "rejected_predictions": loc_result.rejected_predictions,
    }


async def _pipeline_generator(
    repo_url: str,
    issue_text: str,
    analysis_id: str,
) -> AsyncGenerator[str, None]:
    timestamp = datetime.now(timezone.utc).isoformat()

    yield _sse("started", {
        "analysis_id": analysis_id,
        "stage": "cloning",
        "message": "Cloning repository...",
        "timestamp": timestamp,
    })

    # ── Clone ─────────────────────────────────────────────────────────
    try:
        local_path, commit_hash = await _run_in_thread(clone_repository, repo_url)
    except ValueError as exc:
        err = str(exc)
        if "exit code(128)" in err or "Repository not found" in err:
            err = (f"Repository not found: {repo_url}\n"
                   "Make sure the URL is correct and the repository is public.")
        yield _sse("error", {"stage": "cloning", "message": err})
        return

    yield _sse("progress", {
        "stage": "parsing",
        "message": "Cloned. Parsing source files...",
        "commit_hash": commit_hash,
    })

    # ── Parse ─────────────────────────────────────────────────────────
    try:
        repo_root    = Path(local_path)
        language     = _detect_language(repo_root)
        source_files = scan_source_files(local_path, language)

        if not source_files:
            yield _sse("error", {
                "stage": "parsing",
                "message": (f"No source files found for language '{language}'.\n"
                            "Supported: Python (.py), JavaScript/TypeScript (.js .ts .jsx .tsx)"),
            })
            return

        parser    = MultiFileParser(language=language)
        functions = await _run_in_thread(parser.parse_repository, source_files, repo_root)

        if not functions:
            yield _sse("error", {
                "stage": "parsing",
                "message": "Could not extract any functions from the repository.",
            })
            return

    except Exception as exc:
        yield _sse("error", {"stage": "parsing", "message": f"Parsing failed: {exc}"})
        return

    source_count = sum(1 for f in source_files if is_source_file(str(f)))
    test_count   = sum(1 for f in source_files if is_test_file(str(f)))

    yield _sse("progress", {
        "stage": "localizing",
        "message": (
            f"Parsed {len(functions)} functions "
            f"({source_count} source, {test_count} test files). "
            f"Running keyword + structural search..."
        ),
        "detected_language":  language,
        "total_functions":    len(functions),
        "total_files":        len(source_files),
        "source_files":       source_count,
        "test_files":         test_count,
        "commit_hash":        commit_hash,
    })

    # ── Approach A: Keyword ───────────────────────────────────────────
    keyword_result = None
    try:
        keyword_result = await _run_in_thread(
            _keyword_localizer.localize,
            issue_id=analysis_id[:8], issue_text=issue_text,
            functions=functions, repo_url=repo_url,
            commit_hash=commit_hash, top_k=settings.rag_top_k,
        )
        yield _sse("approach_done", _approach_done_payload("keyword", keyword_result))
    except Exception as exc:
        logger.error("[Keyword] %s", exc)
        yield _sse("approach_done", {
            "approach": "keyword", "status": "API_ERROR",
            "predictions": [], "error": str(exc),
        })

    # ── Approach B: Structural ────────────────────────────────────────
    structural_result = None
    try:
        structural_result = await _run_in_thread(
            _structural_localizer.localize,
            issue_id=analysis_id[:8], issue_text=issue_text,
            functions=functions, repo_url=repo_url,
            commit_hash=commit_hash, top_k=settings.rag_top_k,
        )
        yield _sse("approach_done", _approach_done_payload("structural", structural_result))
    except Exception as exc:
        logger.error("[Structural] %s", exc)
        yield _sse("approach_done", {
            "approach": "structural", "status": "API_ERROR",
            "predictions": [], "error": str(exc),
        })

    # ── Embedding (Ollama, with keepalive) ────────────────────────────
    yield _sse("progress", {
        "stage":   "embedding",
        "message": f"Building semantic index ({len(functions)} chunks)...",
    })

    vector_store   = CodeVectorStore(model_name=settings.embedding_model)
    indexed_chunks = 0
    try:
        fut, pings = await _run_llm_with_keepalive(vector_store.build, functions)
        async for ping in pings:
            yield ping
        await fut
        indexed_chunks = vector_store.size
        yield _sse("progress", {
            "stage":             "embedding_done",
            "message":           f"Semantic index ready ({indexed_chunks} chunks, backend={vector_store.backend_used}). Starting LLM...",
            "indexed_chunks":    indexed_chunks,
            "embedding_model":   vector_store.actual_model_used,
            "embedding_backend": vector_store.backend_used,
        })
    except Exception as exc:
        logger.error("[Embedding] %s", exc)
        yield _sse("progress", {
            "stage": "embedding_failed",
            "message": f"Embedding failed: {exc}",
        })

    # ── Repo stats (emit after indexing) ─────────────────────────────
    try:
        repo_stats_dict = _build_repo_stats_dict(
            repo_url, commit_hash, language,
            source_files, functions, indexed_chunks,
        )
        yield _sse("repo_stats", repo_stats_dict)
    except Exception as exc:
        logger.warning("[RepoStats] %s", exc)

    # ── Approach C: LLM Only ─────────────────────────────────────────
    yield _sse("progress", {
        "stage":   "llm_only",
        "message": "LLM-only localization running... (source-code sample, no vector retrieval)",
        "pipeline": [
            "Issue",
            "→ Source context selection (no RAG)",
            "→ LLM reasoning",
            "→ Structured prediction",
            "→ Candidate validation",
        ],
    })
    llm_only_result = None
    try:
        fut, pings = await _run_llm_with_keepalive(
            _llm_only_localizer.localize,
            issue_id=analysis_id[:8], issue_text=issue_text,
            functions=functions, repo_url=repo_url,
            commit_hash=commit_hash, top_k=settings.rag_top_k,
        )
        async for ping in pings:
            yield ping
        llm_only_result = await fut
        yield _sse("approach_done", _approach_done_payload("llm_only", llm_only_result))
    except Exception as exc:
        logger.error("[LLM-Only] %s", exc)
        yield _sse("approach_done", {
            "approach": "llm_only", "status": "API_ERROR",
            "predictions": [], "error": str(exc),
        })

    # ── Approach D: RAG + LLM ────────────────────────────────────────
    yield _sse("progress", {
        "stage":   "rag_llm",
        "message": "RAG + LLM running... (embedding retrieval → dependency expansion → LLM)",
        "pipeline": [
            "Issue",
            "→ Issue embedding",
            "→ FAISS vector retrieval",
            "→ Top-K code chunks",
            "→ Dependency expansion",
            "→ LLM with evidence",
            "→ Validated predictions",
        ],
    })
    rag_llm_result = None
    try:
        if vector_store.size > 0:
            rag_localizer = RAGLLMLocalizer(vector_store=vector_store)
            fut, pings = await _run_llm_with_keepalive(
                rag_localizer.localize,
                issue_id=analysis_id[:8], issue_text=issue_text,
                functions=functions, repo_url=repo_url,
                commit_hash=commit_hash, top_k=settings.rag_top_k,
            )
            async for ping in pings:
                yield ping
            rag_llm_result = await fut
            yield _sse("approach_done", _approach_done_payload("rag_llm", rag_llm_result))
        else:
            yield _sse("approach_done", {
                "approach": "rag_llm", "status": "EMPTY_RESPONSE",
                "predictions": [],
                "error": "Vector store empty — embedding step failed",
            })
    except Exception as exc:
        logger.error("[RAG+LLM] %s", exc)
        yield _sse("approach_done", {
            "approach": "rag_llm", "status": "API_ERROR",
            "predictions": [], "error": str(exc),
        })

    # ── Primary predictions (source files only) ───────────────────────
    def _src_preds(r):
        return [p for p in r.predictions if not p.is_test_file] if r else []

    primary = (
        _src_preds(rag_llm_result)
        or _src_preds(llm_only_result)
        or _src_preds(structural_result)
        or _src_preds(keyword_result)
    )
    # Fallback if all returned test-only
    if not primary:
        for r in [rag_llm_result, llm_only_result, structural_result, keyword_result]:
            if r and r.predictions:
                primary = r.predictions
                break

    if not primary:
        yield _sse("error", {
            "stage":   "localization",
            "message": "All localization approaches returned empty predictions.",
        })
        return

    yield _sse("predictions_ready", {
        "primary_predictions": [p.model_dump() for p in primary],
        "top_file":     primary[0].file,
        "top_function": primary[0].function,
        "top_lines":    f"{primary[0].line_start}–{primary[0].line_end}",
        "message": f"Primary: {primary[0].file} :: {primary[0].function}()",
    })

    # ── Explanation ───────────────────────────────────────────────────
    yield _sse("progress", {"stage": "explanation", "message": "Generating bug explanation..."})
    bug_explanation = None
    try:
        fut, pings = await _run_llm_with_keepalive(
            _explainer.explain,
            issue_text=issue_text, predictions=primary, functions=functions,
        )
        async for ping in pings:
            yield ping
        bug_explanation = await fut
        if bug_explanation:
            yield _sse("explanation_done", {
                "bug_explanation": bug_explanation.model_dump(),
                "message": "Bug explanation ready.",
            })
    except Exception as exc:
        logger.error("[Explanation] %s", exc)

    # ── Fix ───────────────────────────────────────────────────────────
    yield _sse("progress", {"stage": "fix", "message": "Generating proposed fix..."})
    proposed_fix = None
    try:
        fut, pings = await _run_llm_with_keepalive(
            _fix_generator.generate,
            issue_text=issue_text,
            top_prediction=primary[0],
            explanation=bug_explanation,
            functions=functions,
        )
        async for ping in pings:
            yield ping
        proposed_fix = await fut
        if proposed_fix:
            yield _sse("fix_done", {
                "proposed_fix": proposed_fix.model_dump(),
                "message": "Proposed fix ready.",
            })
    except Exception as exc:
        logger.error("[Fix] %s", exc)

    # ── Build final result ────────────────────────────────────────────
    def _preds(r):
        return [p.model_dump() for p in r.predictions] if r else []

    def _summary(approach_str, res):
        if not res:
            return {"approach": approach_str, "status": "EMPTY_RESPONSE", "error": "Not run"}
        top = next((p for p in res.predictions if not p.is_test_file), None)
        return {
            "approach":               approach_str,
            "status":                 res.status,
            "top_prediction_file":    top.file if top else None,
            "top_prediction_function": top.function if top else None,
            "top_prediction_rank":    top.rank if top else None,
            "evidence_strength":      top.evidence_strength.value if top else None,
            "latency_ms":             res.latency_ms,
            "error":                  res.error,
        }

    def _chunk_details(res):
        if not res:
            return []
        return [
            {
                "chunk_id": c.chunk_id,
                "file": c.file,
                "function": c.function,
                "class_name": c.class_name,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "similarity_score": c.similarity_score,
                "code_preview": c.code_preview,
            }
            for c in res.retrieved_chunk_details
        ]

    result_data = {
        "analysis_id":       analysis_id,
        "status":            "completed",
        "repo_url":          repo_url,
        "commit_hash":       commit_hash,
        "detected_language": language,
        "issue_description": issue_text,
        "timestamp":         timestamp,
        "repo_stats":        _build_repo_stats_dict(
            repo_url, commit_hash, language,
            source_files, functions, indexed_chunks,
        ),
        "approach_summaries": [
            _summary("keyword",    keyword_result),
            _summary("structural", structural_result),
            _summary("llm_only",   llm_only_result),
            _summary("rag_llm",    rag_llm_result),
        ],
        "approach_details": [
            _approach_done_payload("keyword",    keyword_result),
            _approach_done_payload("structural", structural_result),
            _approach_done_payload("llm_only",   llm_only_result),
            _approach_done_payload("rag_llm",    rag_llm_result),
        ],
        "primary_predictions":    [p.model_dump() for p in primary],
        "keyword_predictions":    _preds(keyword_result),
        "structural_predictions": _preds(structural_result),
        "llm_only_predictions":   _preds(llm_only_result),
        "rag_llm_predictions":    _preds(rag_llm_result),
        "rag_retrieved_chunks":   _chunk_details(rag_llm_result),
        "bug_explanation": bug_explanation.model_dump() if bug_explanation else None,
        "proposed_fix":    proposed_fix.model_dump() if proposed_fix else None,
        "verification":    None,
        "error":           None,
    }

    yield _sse("completed", {
        "analysis_id": analysis_id,
        "message":     "Analysis complete!",
        "result":      result_data,
    })


@stream_router.post("/repositories/analyze/stream")
async def analyze_stream(request: StreamRequest):
    analysis_id = str(uuid.uuid4())

    async def generator():
        async for chunk in _pipeline_generator(
            request.repo_url, request.issue_description, analysis_id
        ):
            yield chunk

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
