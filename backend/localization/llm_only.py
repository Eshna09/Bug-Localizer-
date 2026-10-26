"""
Approach C — LLM Without RAG.

The LLM receives the issue + a controlled sample of SOURCE-ONLY repository code.
No FAISS vector retrieval is used — this measures pure LLM reasoning capability.

Key fixes (Phase 2):
  1. Path normalization: Windows backslashes ↔ forward slashes (LLM always uses /)
  2. Multi-strategy lookup: exact path, forward-slash normalized, filename-only, stem-only
  3. Fuzzy function matching: strip common prefixes/suffixes that LLMs hallucinate
  4. Invalid predictions are preserved as rejected_predictions (never silently dropped)
  5. Status codes: SUCCESS | TIMEOUT | API_ERROR | PARSING_ERROR | EMPTY_RESPONSE
  6. Explicit pipeline_stages list for UI visibility
"""
from __future__ import annotations
import logging
import re
import time
from pathlib import PurePosixPath, PureWindowsPath
from typing import List, Optional, Tuple

from core.models import (
    FunctionUnit,
    LocalizationApproach,
    LocalizationResult,
    PredictedLocation,
    EvidenceStrength,
)
from localization.llm_client import get_llm_client
from localization.prompts import LLM_ONLY_SYSTEM, LLM_ONLY_USER, PROMPT_VERSION
from localization.file_classifier import is_source_file, is_test_file
from config.settings import settings

logger = logging.getLogger(__name__)

MAX_SAMPLE_CHARS      = 5_000
MAX_VERBATIM_FUNCTIONS = 20


# ---------------------------------------------------------------------------
# Path normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_path(p: str) -> str:
    """Convert any path to forward-slash, lower-case for comparison."""
    return p.replace("\\", "/").lower().strip("/")


def _build_lookup_index(functions: List[FunctionUnit]) -> dict:
    """
    Build a multi-key lookup index for fast validation.

    Keys stored (all lower-cased, forward-slashed):
      (norm_full_path, norm_fn_name)     → FunctionUnit
      (filename_only,  norm_fn_name)     → FunctionUnit
      (stem_only,      norm_fn_name)     → FunctionUnit

    This lets us match:
      "app/services/discount_service.py" :: "calculate_discount"
      even when the parser stored "app\\services\\discount_service.py"
    """
    index: dict[tuple[str, str], FunctionUnit] = {}

    for u in functions:
        norm_path = _normalise_path(u.file_path)
        norm_fn   = u.function_name.lower()
        filename  = PurePosixPath(norm_path).name          # "discount_service.py"
        stem      = PurePosixPath(norm_path).stem           # "discount_service"

        for path_key in [norm_path, filename, stem]:
            key = (path_key, norm_fn)
            if key not in index:
                index[key] = u

    return index


def _lookup_unit(
    file_pred: str,
    fn_pred: str,
    index: dict,
) -> Optional[FunctionUnit]:
    """
    Try multiple normalisation strategies to match an LLM prediction
    against the real repository index.

    Returns the matched FunctionUnit or None.
    """
    norm_file = _normalise_path(file_pred)
    norm_fn   = fn_pred.lower().strip()

    filename = PurePosixPath(norm_file).name
    stem     = PurePosixPath(norm_file).stem

    # Strategy 1: exact normalised match
    for path_key in [norm_file, filename, stem]:
        u = index.get((path_key, norm_fn))
        if u:
            return u

    # Strategy 2: partial path suffix match  (e.g. LLM says "services/discount_service.py")
    for (pk, fk), u in index.items():
        if norm_file.endswith(pk) or pk.endswith(norm_file):
            if fk == norm_fn:
                return u

    # Strategy 3: file match, fuzzy function name (LLM may add/drop underscores/prefixes)
    for (pk, fk), u in index.items():
        file_match = (pk == norm_file or pk == filename or pk == stem
                      or norm_file.endswith(pk) or pk.endswith(norm_file))
        if file_match:
            # Fuzzy: one is a substring of the other
            if norm_fn in fk or fk in norm_fn:
                return u

    return None


# ---------------------------------------------------------------------------
# Code sample builder
# ---------------------------------------------------------------------------

def _build_code_sample(functions: List[FunctionUnit], max_chars: int = MAX_SAMPLE_CHARS) -> Tuple[str, int]:
    """
    Build a controlled sample of SOURCE-ONLY repository code.
    Paths are always shown as forward-slash so the LLM produces consistent output.
    Returns (sample_text, context_size_chars).
    """
    source_fns = [u for u in functions if is_source_file(u.file_path)]
    if not source_fns:
        source_fns = functions

    lines: List[str] = []
    total = 0

    for i, unit in enumerate(source_fns):
        # Always use forward slashes in prompt
        fwd_path = unit.file_path.replace("\\", "/")

        if i < MAX_VERBATIM_FUNCTIONS:
            snippet = (
                f"# FILE: {fwd_path}\n"
                f"# Lines {unit.start_line}-{unit.end_line}\n"
                f"{unit.source_code[:600]}\n"
            )
        else:
            snippet = f"# FILE: {fwd_path} | def {unit.function_name}() line {unit.start_line}\n"

        if total + len(snippet) > max_chars:
            lines.append(f"# ... ({len(source_fns) - i} more functions omitted)")
            break
        lines.append(snippet)
        total += len(snippet)

    sample = "\n".join(lines)
    return sample, len(sample)


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _try_extract_json(text: str) -> Optional[dict]:
    """Aggressively extract a JSON object from raw LLM output."""
    import json

    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
    text = text.strip()

    # Strip markdown fences
    if "```" in text:
        inner = re.sub(r'^```[a-z]*\n?', '', text, count=1)
        inner = re.sub(r'\n?```\s*$', '', inner)
        text = inner.strip()

    # Strip <json>...</json>
    json_tag = re.search(r'<json>(.*?)</json>', text, re.DOTALL | re.IGNORECASE)
    if json_tag:
        text = json_tag.group(1).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except Exception:
            pass

    arr_match = re.search(r'"predictions"\s*:\s*(\[.*?\])', text, re.DOTALL)
    if arr_match:
        try:
            preds = json.loads(arr_match.group(1))
            return {"predictions": preds}
        except Exception:
            pass

    return None


def _heuristic_extract(text: str, functions: List[FunctionUnit]) -> List[dict]:
    """Last-resort heuristic extraction from LLM prose."""
    index = _build_lookup_index(functions)
    found: List[dict] = []
    seen_chunks: set = set()

    patterns = [
        r'`?([a-zA-Z0-9_/\\\.]+\.(?:py|js|ts|jsx|tsx))`?\s*[:\-–]\s*[`\'"]?(\w+)[`\'"]?',
        r'function\s+`?(\w+)`?',
        r'in\s+`?(\w+)`?\s+(?:function|method)',
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            groups = m.groups()
            for (pk, fk), u in index.items():
                if any(g and (g.lower() in pk or g.lower() == fk) for g in groups):
                    if u.chunk_id not in seen_chunks and is_source_file(u.file_path):
                        seen_chunks.add(u.chunk_id)
                        found.append({
                            "rank": len(found) + 1,
                            "file": u.file_path.replace("\\", "/"),
                            "function": u.function_name,
                            "line_start": u.start_line,
                            "line_end": u.end_line,
                            "reason": f"Heuristic match from prose: {m.group(0)[:80]}",
                            "evidence_strength": "Low",
                        })
                        if len(found) >= 3:
                            return found
    return found


# ---------------------------------------------------------------------------
# Prediction parser + validator
# ---------------------------------------------------------------------------

def _parse_and_validate_predictions(
    raw: dict,
    functions: List[FunctionUnit],
) -> Tuple[List[PredictedLocation], List[dict]]:
    """
    Parse LLM JSON predictions and validate against real repository.

    Returns:
        (valid_predictions, rejected_items)
        - valid_predictions: matched and resolved against actual functions
        - rejected_items: list of dicts with reason, for research integrity reporting
    """
    index  = _build_lookup_index(functions)
    raw_preds = raw.get("predictions", [])
    if not isinstance(raw_preds, list):
        raw_preds = []

    valid:    List[PredictedLocation] = []
    rejected: List[dict] = []

    for item in raw_preds:
        if not isinstance(item, dict):
            rejected.append({"item": str(item), "reason": "not a dict"})
            continue

        file_pred = str(item.get("file", "")).strip()
        fn_pred   = str(item.get("function", "")).strip()

        if not file_pred or not fn_pred:
            rejected.append({
                "file": file_pred, "function": fn_pred,
                "reason": "empty file or function field",
            })
            continue

        unit = _lookup_unit(file_pred, fn_pred, index)

        if unit is None:
            # Record rejection with full details for research reporting
            rejected.append({
                "file": file_pred,
                "function": fn_pred,
                "reason": f"not found in repository index (tried normalised path, filename-only, stem-only, suffix-match, fuzzy-fn)",
                "llm_line_start": item.get("line_start"),
                "llm_line_end": item.get("line_end"),
            })
            logger.warning(
                "[LLM-Only] REJECTED: file=%r fn=%r — no matching function in repo index",
                file_pred, fn_pred,
            )
            continue

        strength_raw = item.get("evidence_strength", item.get("confidence", "Low"))
        try:
            strength = EvidenceStrength(str(strength_raw).capitalize())
        except ValueError:
            strength = EvidenceStrength.LOW

        is_test = is_test_file(unit.file_path)
        ctype   = "supporting_evidence" if is_test else "primary"

        valid.append(PredictedLocation(
            rank=item.get("rank", len(valid) + 1),
            file=unit.file_path.replace("\\", "/"),   # canonical forward-slash
            function=unit.function_name,
            class_name=unit.class_name,
            line_start=unit.start_line,
            line_end=unit.end_line,
            reason=item.get("reason", item.get("reasoning", "")),
            evidence_strength=strength,
            source_code=unit.source_code,
            is_test_file=is_test,
            candidate_type=ctype,
        ))
        logger.info(
            "[LLM-Only] VALIDATED: %s :: %s (L%d–%d)",
            unit.file_path, unit.function_name, unit.start_line, unit.end_line,
        )

    # Sort: primary first, then supporting
    valid.sort(key=lambda p: (1 if p.is_test_file else 0, p.rank))
    for i, pred in enumerate(valid, start=1):
        pred.rank = i

    return valid, rejected


# ---------------------------------------------------------------------------
# Localizer
# ---------------------------------------------------------------------------

class LLMOnlyLocalizer:
    """
    Approach C: LLM localization without RAG.
    Source-only code sample — no vector retrieval.
    """

    def localize(
        self,
        issue_id: str,
        issue_text: str,
        functions: List[FunctionUnit],
        repo_url: str,
        commit_hash: str,
        top_k: int = 5,
    ) -> LocalizationResult:
        start  = time.time()
        stages: List[str] = []

        client = get_llm_client()
        stages.append("context_selection")

        code_sample, context_size = _build_code_sample(functions)
        source_count = sum(1 for u in functions if is_source_file(u.file_path))
        stages.append("prompt_built")

        logger.info(
            "[LLM-Only] Sending %d chars to LLM (%d source functions)",
            context_size, source_count,
        )

        user_prompt = LLM_ONLY_USER.format(
            issue_text=issue_text,
            repo_url=repo_url,
            commit_hash=commit_hash,
            code_sample=code_sample,
            source_file_count=source_count,
        )

        # ── LLM call ─────────────────────────────────────────────────
        try:
            raw_text, usage = client.complete(
                system_prompt=LLM_ONLY_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=400,   # a 5-prediction JSON is ~200-300 tokens; 400 gives headroom
                temperature=0.0,
            )
            stages.append("llm_response_received")
            logger.info("[LLM-Only] Raw response (%d chars): %s", len(raw_text), raw_text[:400])
        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            err_str = str(exc)
            status  = "TIMEOUT" if "timeout" in err_str.lower() else "API_ERROR"
            logger.error("[LLM-Only] LLM call failed (%s): %s", status, exc)
            return LocalizationResult(
                approach=LocalizationApproach.LLM_ONLY,
                issue_id=issue_id, repository=repo_url, commit_hash=commit_hash,
                predictions=[], model=settings.llm_model,
                prompt_version=PROMPT_VERSION, latency_ms=elapsed,
                status=status, error=str(exc),
                pipeline_stages=stages, context_size_chars=context_size,
            )

        # ── Parse ────────────────────────────────────────────────────
        stages.append("parsing")
        raw_dict = _try_extract_json(raw_text)

        if raw_dict is None:
            logger.warning("[LLM-Only] JSON parse failed, trying heuristic extraction")
            stages.append("heuristic_fallback")
            heuristic_items = _heuristic_extract(raw_text, functions)
            if heuristic_items:
                raw_dict = {"predictions": heuristic_items}
                logger.info("[LLM-Only] Heuristic extracted %d items", len(heuristic_items))
            else:
                elapsed = (time.time() - start) * 1000
                return LocalizationResult(
                    approach=LocalizationApproach.LLM_ONLY,
                    issue_id=issue_id, repository=repo_url, commit_hash=commit_hash,
                    predictions=[], model=settings.llm_model,
                    prompt_version=PROMPT_VERSION, latency_ms=elapsed,
                    status="PARSING_ERROR",
                    error=f"LLM response not parseable as JSON or prose. Preview: {raw_text[:300]}",
                    pipeline_stages=stages, context_size_chars=context_size, token_usage=usage,
                )

        # ── Validate ─────────────────────────────────────────────────
        stages.append("validation")
        predictions, rejected = _parse_and_validate_predictions(raw_dict, functions)

        elapsed = (time.time() - start) * 1000

        if rejected:
            logger.warning(
                "[LLM-Only] %d predictions rejected: %s",
                len(rejected),
                "; ".join(f"{r['file']}::{r['function']} ({r['reason']})" for r in rejected if 'file' in r),
            )

        if not predictions:
            return LocalizationResult(
                approach=LocalizationApproach.LLM_ONLY,
                issue_id=issue_id, repository=repo_url, commit_hash=commit_hash,
                predictions=[], model=settings.llm_model,
                prompt_version=PROMPT_VERSION, latency_ms=elapsed,
                status="EMPTY_RESPONSE",
                error=(
                    f"LLM returned {len(rejected)} prediction(s) but none matched real repository functions. "
                    f"Rejected: {[r.get('file','?')+'::'+r.get('function','?') for r in rejected]}. "
                    f"Raw: {raw_text[:200]}"
                ),
                pipeline_stages=stages, context_size_chars=context_size, token_usage=usage,
            )

        stages.append("complete")
        source_preds = [p for p in predictions if not p.is_test_file]
        test_preds   = [p for p in predictions if p.is_test_file]

        logger.info(
            "[LLM-Only] %d valid predictions (%d source, %d test) in %.1f ms",
            len(predictions), len(source_preds), len(test_preds), elapsed,
        )

        return LocalizationResult(
            approach=LocalizationApproach.LLM_ONLY,
            issue_id=issue_id, repository=repo_url, commit_hash=commit_hash,
            predictions=predictions[:top_k],
            model=settings.llm_model, prompt_version=PROMPT_VERSION,
            latency_ms=elapsed, token_usage=usage,
            status="SUCCESS",
            pipeline_stages=stages, context_size_chars=context_size,
            num_source_predictions=len(source_preds),
            num_test_predictions=len(test_preds),
            rejected_predictions=rejected,
        )
