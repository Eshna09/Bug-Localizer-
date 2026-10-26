"""
Fix generator.
Produces a minimal, safe proposed fix for the identified bug.
Runs AFTER localization and explanation are recorded.
Never modifies the original repository.

Performance notes (codellama:7b):
- max_tokens capped at 500 so the call completes in ~30s instead of ~90s
- Source code truncated to 600 chars to keep prompt under 2000 tokens
- Returns None gracefully if LLM produces unusable output
"""
from __future__ import annotations
import difflib
import json
import logging
import re
from typing import List, Optional

from core.models import (
    FunctionUnit,
    PredictedLocation,
    BugExplanation,
    ProposedFix,
)
from localization.llm_client import get_llm_client
from localization.prompts import FIX_SYSTEM, FIX_USER

logger = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 600
MAX_TOKENS       = 500   # keeps codellama:7b response time under ~35s


def _generate_diff(current: str, proposed: str, file_path: str, function_name: str) -> str:
    current_lines  = current.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)
    diff = difflib.unified_diff(
        current_lines, proposed_lines,
        fromfile=f"a/{file_path} [current]",
        tofile=f"b/{file_path} [proposed]",
        lineterm="",
    )
    return "".join(diff)


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from potentially truncated LLM output."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(clean)
    except Exception:
        pass
    brace = re.search(r'\{.*\}', clean, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(0))
        except Exception:
            pass

    # Last resort: look for proposed_code as a bare string
    code_match = re.search(r'"proposed_code"\s*:\s*"(.*?)"(?:,|\})', clean, re.DOTALL)
    if code_match:
        return {"proposed_code": code_match.group(1).replace("\\n", "\n")}

    return None


class FixGenerator:
    """
    Generates a minimal proposed fix for the identified bug location.
    Designed to complete quickly with local 7B models.
    """

    def generate(
        self,
        issue_text: str,
        top_prediction: PredictedLocation,
        explanation: Optional[BugExplanation],
        functions: List[FunctionUnit],
    ) -> Optional[ProposedFix]:
        if not top_prediction.source_code:
            logger.warning("No source code available for fix generation.")
            return None

        explanation_text = ""
        if explanation:
            explanation_text = (
                f"Bug: {explanation.what_is_wrong}\n"
                f"Cause: {explanation.why_is_it_wrong}\n"
                f"Expected: {explanation.what_should_happen}"
            )[:400]
        else:
            explanation_text = issue_text[:200]

        user_prompt = FIX_USER.format(
            issue_text=issue_text,
            file=top_prediction.file,
            function=top_prediction.function,
            line_start=top_prediction.line_start,
            line_end=top_prediction.line_end,
            current_code=top_prediction.source_code[:MAX_SOURCE_CHARS],
            explanation=explanation_text,
        )

        client = get_llm_client()
        try:
            raw_text, _ = client.complete(
                system_prompt=FIX_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=MAX_TOKENS,
                temperature=0.0,
            )
        except Exception as exc:
            logger.error("Fix generation failed: %s", exc)
            return None

        raw = _extract_json(raw_text)
        if not raw:
            logger.warning("Fix JSON parse failed. Raw: %s", raw_text[:200])
            return None

        proposed_code = raw.get("proposed_code", "").strip()
        if not proposed_code:
            logger.warning("LLM returned empty proposed_code.")
            return None

        if proposed_code == top_prediction.source_code.strip():
            logger.warning("Proposed code identical to current — no fix generated.")
            return None

        diff = _generate_diff(
            top_prediction.source_code,
            proposed_code,
            top_prediction.file,
            top_prediction.function,
        )

        return ProposedFix(
            file=top_prediction.file,
            function=top_prediction.function,
            current_code=top_prediction.source_code,
            proposed_code=proposed_code,
            diff=diff,
            minimal_change_description=raw.get("diff_description", ""),
            why_this_fixes=raw.get("why_this_fixes", ""),
            what_changed=raw.get("changed_lines", []),
            why_safe=raw.get("why_safe", ""),
            potential_side_effects=raw.get("potential_side_effects", ""),
            is_minimal=raw.get("is_minimal", True),
        )
