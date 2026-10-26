"""
Approach D — RAG + LLM (Primary Research Approach).

Pipeline:
  Issue text
    → Embedding (nomic-embed-text / sentence-transformers)
    → FAISS retrieval (top-K chunks) — SOURCE files prioritised
    → Metadata filtering (exclude test files from primary results)
    → Optional dependency/call-graph expansion
    → Retrieved context formatted for LLM
    → Structured LLM prompt with evidence
    → JSON parse (with fallback heuristics)
    → Candidate validation against real repository
    → Ranking (source files before test files)

Explicitly differs from LLM-only:
  - Uses vector retrieval (semantic similarity)
  - LLM sees ONLY the retrieved chunks, not a sampled dump
  - Retrieved chunks are exposed in the result for UI display
  - Dependency expansion adds structural context the LLM-only approach lacks
"""
from __future__ import annotations
import logging
import time
from typing import List, Dict

from core.models import (
    FunctionUnit,
    LocalizationApproach,
    LocalizationResult,
    PredictedLocation,
    EvidenceStrength,
    RetrievedChunkDetail,
)
from localization.embeddings import CodeVectorStore, RetrievedChunk
from localization.llm_client import get_llm_client
from localization.llm_only import _parse_and_validate_predictions, _try_extract_json, _heuristic_extract
from localization.prompts import RAG_LLM_SYSTEM, RAG_LLM_USER, PROMPT_VERSION
from localization.file_classifier import is_source_file, is_test_file
from config.settings import settings

logger = logging.getLogger(__name__)

# Max chars per chunk shown to the LLM
CHUNK_PREVIEW_CHARS = 300   # reduced from 500 — leaves more token budget for LLM response
# Max chunks to send in the LLM prompt (fewer = more room for response)
MAX_LLM_CHUNKS = 4


def _format_retrieved_chunks(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved chunks for the LLM prompt. Always use forward-slash paths."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        m = chunk.metadata
        code_preview = m.source_code[:CHUNK_PREVIEW_CHARS]
        if len(m.source_code) > CHUNK_PREVIEW_CHARS:
            code_preview += "..."
        # Always forward-slash so the LLM returns consistent paths
        fwd_path  = m.file_path.replace("\\", "/")
        file_type = "TEST" if is_test_file(m.file_path) else "SOURCE"
        parts.append(
            f"--- CHUNK {i} [{file_type}] (similarity: {chunk.score:.3f}) ---\n"
            f"File: {fwd_path}\n"
            f"Function: {m.function_name}\n"
            f"Lines: {m.start_line}–{m.end_line}\n"
            f"Chunk ID: {m.chunk_id}\n"
            f"```\n{code_preview}\n```"
        )
    return "\n\n".join(parts)


def _expand_with_dependencies(
    retrieved: List[RetrievedChunk],
    functions: List[FunctionUnit],
    max_additional: int = 3,
) -> tuple[List[RetrievedChunk], str]:
    """Expand retrieved chunks with caller/callee context from call graph."""
    from localization.embeddings import RetrievedChunk as RC, ChunkMetadata

    chunk_id_to_unit: Dict[str, FunctionUnit] = {u.chunk_id: u for u in functions}
    name_to_units: Dict[str, List[FunctionUnit]] = {}
    for u in functions:
        name_to_units.setdefault(u.function_name, []).append(u)

    already_seen = {c.metadata.chunk_id for c in retrieved}
    additional: List[FunctionUnit] = []
    dependency_lines: List[str] = []

    for chunk in retrieved:
        unit = chunk_id_to_unit.get(chunk.metadata.chunk_id)
        if not unit:
            continue

        for caller_name in unit.called_by[:2]:
            for caller_unit in name_to_units.get(caller_name, []):
                if caller_unit.chunk_id not in already_seen:
                    additional.append(caller_unit)
                    already_seen.add(caller_unit.chunk_id)
                    dependency_lines.append(
                        f"  {caller_name}() → {unit.function_name}() [{unit.file_path}]"
                    )

        for callee_name in unit.calls[:2]:
            for callee_unit in name_to_units.get(callee_name, []):
                if callee_unit.chunk_id not in already_seen:
                    additional.append(callee_unit)
                    already_seen.add(callee_unit.chunk_id)
                    dependency_lines.append(
                        f"  {unit.function_name}() → {callee_name}() [{callee_unit.file_path}]"
                    )

    dep_context = "\n".join(dependency_lines) if dependency_lines else "No additional dependencies resolved."

    extra_chunks: List[RC] = []
    for unit in additional[:max_additional]:
        extra_chunks.append(RC(
            metadata=ChunkMetadata(
                chunk_id=unit.chunk_id,
                file_path=unit.file_path,
                class_name=unit.class_name,
                function_name=unit.function_name,
                start_line=unit.start_line,
                end_line=unit.end_line,
                source_code=unit.source_code,
            ),
            score=0.0,
        ))

    return retrieved + extra_chunks, dep_context


class RAGLLMLocalizer:
    """
    Approach D: RAG + LLM — primary research approach.

    Differs from LLM-Only:
      - Dynamic semantic retrieval via FAISS (not static sampling)
      - LLM sees only the most relevant chunks
      - Retrieved chunks are fully exposed in the result
      - Dependency expansion adds structural context
    """

    def __init__(self, vector_store: CodeVectorStore):
        self.vector_store = vector_store

    def localize(
        self,
        issue_id: str,
        issue_text: str,
        functions: List[FunctionUnit],
        repo_url: str,
        commit_hash: str,
        top_k: int = 5,
    ) -> LocalizationResult:
        start = time.time()
        stages: List[str] = []

        if self.vector_store.size == 0:
            elapsed = (time.time() - start) * 1000
            return LocalizationResult(
                approach=LocalizationApproach.RAG_LLM,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                status="EMPTY_RESPONSE",
                error="Vector store is empty. Build the index first.",
                latency_ms=elapsed,
                pipeline_stages=stages,
            )

        # ── Step 1: Issue embedding + retrieval ───────────────────────────
        stages.append("issue_embedding")
        try:
            # Retrieve more candidates than top_k so we can filter to source-only
            fetch_k = max(top_k * 3, 15)
            retrieved = self.vector_store.retrieve(issue_text, top_k=fetch_k)
            stages.append("vector_retrieval")
            logger.info("[RAG+LLM] Retrieved %d chunks (fetch_k=%d)", len(retrieved), fetch_k)
        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            return LocalizationResult(
                approach=LocalizationApproach.RAG_LLM,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                status="API_ERROR",
                error=f"Retrieval failed: {exc}",
                latency_ms=elapsed,
                pipeline_stages=stages,
            )

        # ── Step 2: Metadata filtering — prefer source files for LLM context ─
        stages.append("metadata_filtering")
        source_retrieved = [c for c in retrieved if is_source_file(c.metadata.file_path)]
        test_retrieved   = [c for c in retrieved if is_test_file(c.metadata.file_path)]
        logger.info(
            "[RAG+LLM] After filter: %d source, %d test chunks",
            len(source_retrieved), len(test_retrieved),
        )
        # Show top-K source chunks to LLM; only include test chunks if we don't have enough
        if len(source_retrieved) >= top_k:
            llm_chunks = source_retrieved[:MAX_LLM_CHUNKS]
        elif len(source_retrieved) >= 2:
            remaining = MAX_LLM_CHUNKS - len(source_retrieved)
            llm_chunks = source_retrieved + test_retrieved[:remaining]
        else:
            llm_chunks = retrieved[:MAX_LLM_CHUNKS]

        # For UI display — show all originally retrieved (source + test), sorted by score
        display_retrieved = sorted(retrieved, key=lambda c: c.score, reverse=True)[:top_k * 2]

        # ── Step 3: Dependency expansion ─────────────────────────────────
        stages.append("dependency_expansion")
        expanded_chunks, dep_context = _expand_with_dependencies(llm_chunks, functions)

        # ── Build chunk detail objects for UI display ─────────────────────
        chunk_details: List[RetrievedChunkDetail] = [
            RetrievedChunkDetail(
                chunk_id=c.metadata.chunk_id,
                file=c.metadata.file_path.replace("\\", "/"),
                function=c.metadata.function_name,
                class_name=c.metadata.class_name,
                line_start=c.metadata.start_line,
                line_end=c.metadata.end_line,
                similarity_score=c.score,
                code_preview=c.metadata.source_code[:300],
            )
            for c in display_retrieved
        ]
        chunk_ids = [c.metadata.chunk_id for c in display_retrieved]

        # ── Step 4: Format prompt ─────────────────────────────────────────
        chunks_text = _format_retrieved_chunks(expanded_chunks)
        context_size = len(chunks_text)
        stages.append("prompt_built")

        user_prompt = RAG_LLM_USER.format(
            issue_text=issue_text,
            repo_url=repo_url,
            commit_hash=commit_hash,
            k=len(llm_chunks),
            retrieved_chunks=chunks_text,
            dependency_context=dep_context,
        )

        # ── Step 5: LLM call ──────────────────────────────────────────────
        stages.append("llm_call")
        client = get_llm_client()

        # Calculate remaining tokens for response.
        # codellama:7b context = 4096 tokens. RAG prompt is large (~2500-3500 tokens).
        # Keep response budget reasonable but not so large it causes truncation of the PROMPT.
        # Rule: cap response tokens so total stays under 3800 (safety margin below 4096).
        # Rough estimate: 1 token ≈ 3.5 chars
        estimated_prompt_tokens = len(user_prompt) // 3
        max_response_tokens = max(256, min(800, 3800 - estimated_prompt_tokens))
        logger.info(
            "[RAG+LLM] Estimated prompt tokens: %d, response budget: %d",
            estimated_prompt_tokens, max_response_tokens,
        )

        try:
            raw_text, usage = client.complete(
                system_prompt=RAG_LLM_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=max_response_tokens,
                temperature=0.0,
            )
            stages.append("llm_response_received")
        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            err_str = str(exc)
            status = "TIMEOUT" if "timeout" in err_str.lower() else "API_ERROR"
            return LocalizationResult(
                approach=LocalizationApproach.RAG_LLM,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                retrieved_chunks=chunk_ids,
                retrieved_chunk_details=chunk_details,
                model=settings.llm_model,
                embedding_model=settings.embedding_model,
                prompt_version=PROMPT_VERSION,
                latency_ms=elapsed,
                status=status,
                error=str(exc),
                pipeline_stages=stages,
                context_size_chars=context_size,
            )

        # ── Step 6: Parse response ────────────────────────────────────────
        stages.append("parsing")
        raw_dict = _try_extract_json(raw_text)

        if raw_dict is None:
            logger.warning("[RAG+LLM] JSON parse failed, trying heuristic extraction")
            stages.append("heuristic_fallback")
            heuristic_items = _heuristic_extract(raw_text, functions)
            if heuristic_items:
                raw_dict = {"predictions": heuristic_items}
            else:
                elapsed = (time.time() - start) * 1000
                return LocalizationResult(
                    approach=LocalizationApproach.RAG_LLM,
                    issue_id=issue_id,
                    repository=repo_url,
                    commit_hash=commit_hash,
                    predictions=[],
                    retrieved_chunks=chunk_ids,
                    retrieved_chunk_details=chunk_details,
                    model=settings.llm_model,
                    embedding_model=settings.embedding_model,
                    prompt_version=PROMPT_VERSION,
                    latency_ms=elapsed,
                    status="PARSING_ERROR",
                    error=f"LLM response could not be parsed. Preview: {raw_text[:300]}",
                    pipeline_stages=stages,
                    context_size_chars=context_size,
                    token_usage=usage,
                )

        # ── Step 7: Validate predictions ──────────────────────────────────
        stages.append("validation")
        predictions, rejected = _parse_and_validate_predictions(raw_dict, functions)

        # Attach retrieved chunk references to each prediction
        for pred in predictions:
            pred.retrieved_chunks = chunk_ids

        if not predictions:
            elapsed = (time.time() - start) * 1000
            return LocalizationResult(
                approach=LocalizationApproach.RAG_LLM,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                retrieved_chunks=chunk_ids,
                retrieved_chunk_details=chunk_details,
                model=settings.llm_model,
                embedding_model=settings.embedding_model,
                prompt_version=PROMPT_VERSION,
                latency_ms=(time.time() - start) * 1000,
                status="EMPTY_RESPONSE",
                error=f"LLM returned predictions but none matched repository functions. Raw: {raw_text[:300]}",
                pipeline_stages=stages,
                context_size_chars=context_size,
                token_usage=usage,
            )

        elapsed = (time.time() - start) * 1000
        stages.append("complete")
        logger.info("[RAG+LLM] %d valid predictions in %.1f ms", len(predictions), elapsed)

        source_preds = [p for p in predictions if not p.is_test_file]
        test_preds   = [p for p in predictions if p.is_test_file]

        return LocalizationResult(
            approach=LocalizationApproach.RAG_LLM,
            issue_id=issue_id,
            repository=repo_url,
            commit_hash=commit_hash,
            predictions=predictions[:top_k],
            retrieved_chunks=chunk_ids,
            retrieved_chunk_details=chunk_details,
            model=settings.llm_model,
            embedding_model=self.vector_store.actual_model_used,
            prompt_version=PROMPT_VERSION,
            latency_ms=elapsed,
            token_usage=usage,
            status="SUCCESS",
            pipeline_stages=stages,
            context_size_chars=context_size,
            num_source_predictions=len(source_preds),
            num_test_predictions=len(test_preds),
            rejected_predictions=rejected,
        )
