"""
Bug explanation generator.
Runs AFTER localization predictions are recorded.
Produces structured natural-language explanation of the bug.

Performance notes (codellama:7b):
- max_tokens capped at 600 to prevent 90s+ waits
- Source code truncated to 800 chars to keep prompt under 2000 tokens
- JSON fallback handles partial responses gracefully
"""
from __future__ import annotations
import json
import logging
import re
from typing import List, Optional

from core.models import (
    FunctionUnit,
    PredictedLocation,
    BugExplanation,
    RootCause,
    AffectedComponent,
)
from localization.llm_client import get_llm_client
from localization.prompts import EXPLANATION_SYSTEM, EXPLANATION_USER

logger = logging.getLogger(__name__)

# Source code snippet sent to the LLM — keep short to stay under context limit
MAX_SOURCE_CHARS = 800
# Max tokens for explanation response — enough for structured JSON, not a novel
MAX_TOKENS = 600


def _format_affected(predictions: List[PredictedLocation]) -> str:
    if len(predictions) <= 1:
        return "None identified."
    return ", ".join(
        f"{p.file.split('/')[-1]}::{p.function}()" for p in predictions[1:4]
    )


def _extract_json_partial(text: str) -> Optional[dict]:
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
    return None


class BugExplainer:
    """
    Generates structured bug explanation from the top localization prediction.
    Separates root cause from affected code.
    Designed to complete quickly with local 7B models.
    """

    def explain(
        self,
        issue_text: str,
        predictions: List[PredictedLocation],
        functions: List[FunctionUnit],
    ) -> Optional[BugExplanation]:
        if not predictions:
            logger.warning("No predictions to explain.")
            return None

        top = predictions[0]
        affected_text = _format_affected(predictions)
        source_snippet = (top.source_code or "(unavailable)")[:MAX_SOURCE_CHARS]

        user_prompt = EXPLANATION_USER.format(
            issue_text=issue_text,
            file=top.file,
            function=top.function,
            line_start=top.line_start,
            line_end=top.line_end,
            source_code=source_snippet,
            affected=affected_text,
        )

        client = get_llm_client()
        try:
            raw_text, _ = client.complete(
                system_prompt=EXPLANATION_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=MAX_TOKENS,
                temperature=0.0,
            )
        except Exception as exc:
            logger.error("Explanation LLM call failed: %s", exc)
            return None

        raw = _extract_json_partial(raw_text)
        if not raw:
            logger.warning("Explanation JSON parse failed. Raw: %s", raw_text[:200])
            # Build a minimal explanation from the issue text so the UI has something
            return BugExplanation(
                what_is_wrong=issue_text,
                why_is_it_wrong="LLM explanation could not be parsed.",
                what_should_happen="",
                what_actually_happens="",
                downstream_impact="",
                root_cause=RootCause(
                    file=top.file, function=top.function,
                    line_start=top.line_start, line_end=top.line_end,
                    explanation="Root cause identified by localization pipeline.",
                ),
                affected_components=[],
                dependency_chain=[],
            )

        try:
            rc_raw = raw.get("root_cause", {})
            # Ensure root_cause always points to a production file, not a test
            rc_file = rc_raw.get("file", top.file)
            if "test" in rc_file.lower():
                rc_file = top.file

            root_cause = RootCause(
                file=rc_file,
                function=rc_raw.get("function", top.function),
                line_start=rc_raw.get("line_start", top.line_start),
                line_end=rc_raw.get("line_end", top.line_end),
                explanation=rc_raw.get("explanation", raw.get("why_is_it_wrong", "")),
            )

            affected_components = []
            for ac in raw.get("affected_components", []):
                if not isinstance(ac, dict):
                    continue
                affected_components.append(AffectedComponent(
                    file=ac.get("file", ""),
                    function=ac.get("function", ""),
                    how_affected=ac.get("how_affected", ""),
                ))

            return BugExplanation(
                what_is_wrong=raw.get("what_is_wrong", issue_text),
                why_is_it_wrong=raw.get("why_is_it_wrong", ""),
                what_should_happen=raw.get("what_should_happen", ""),
                what_actually_happens=raw.get("what_actually_happens", ""),
                downstream_impact=raw.get("downstream_impact", ""),
                root_cause=root_cause,
                affected_components=affected_components,
                dependency_chain=raw.get("dependency_chain", []),
            )

        except Exception as exc:
            logger.error("Failed to parse explanation response: %s — raw: %s", exc, raw_text[:200])
            return None
