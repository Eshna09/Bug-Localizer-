"""
Prompt templates for all LLM calls.
Versioned for reproducibility.
Designed to be compatible with local models (codellama:7b, deepseek, mistral).
"""
PROMPT_VERSION = "v2.0.0"

# ---------------------------------------------------------------------------
# Approach C: LLM-only localization
# ---------------------------------------------------------------------------

LLM_ONLY_SYSTEM = """You are a software debugging expert. Your job is to find bugs in code.
You will receive a bug report and some source code. Find the most likely bug location.
You MUST respond ONLY with a JSON object. No other text."""

LLM_ONLY_USER = """Bug report: {issue_text}

Repository: {repo_url} (commit: {commit_hash})
Source files ({source_file_count} functions shown):

{code_sample}

Find the bug. Return this JSON (fill in real values from the code above):
{{
  "predictions": [
    {{
      "rank": 1,
      "file": "path/to/file.py",
      "function": "function_name",
      "line_start": 10,
      "line_end": 20,
      "reason": "Why this is the bug location",
      "evidence_strength": "High"
    }}
  ],
  "reasoning_summary": "Brief summary"
}}

Rules:
- Only use files and functions that appear in the code above
- evidence_strength must be: High, Medium, Low, or Insufficient
- Include 1 to 5 predictions"""


# ---------------------------------------------------------------------------
# Approach D: RAG + LLM localization
# ---------------------------------------------------------------------------

RAG_LLM_SYSTEM = """You are a software debugging expert with access to retrieved code evidence.
You will receive a bug report and the most relevant code chunks from the repository.
Find the bug location using the evidence. You MUST respond ONLY with a JSON object."""

RAG_LLM_USER = """Bug report: {issue_text}

Repository: {repo_url} (commit: {commit_hash})

Retrieved evidence (top-{k} most relevant code chunks):
{retrieved_chunks}

Dependency context:
{dependency_context}

Find the bug. Return this JSON (only use files/functions from the evidence above):
{{
  "predictions": [
    {{
      "rank": 1,
      "file": "path/to/file.py",
      "function": "function_name",
      "line_start": 10,
      "line_end": 20,
      "reason": "Specific reasoning based on the retrieved evidence",
      "evidence_strength": "High",
      "supporting_chunk_ids": ["chunk_id_1"]
    }}
  ],
  "reasoning_summary": "Overall reasoning referencing the evidence"
}}

Rules:
- Only reference files and functions in the retrieved evidence
- evidence_strength must be: High, Medium, Low, or Insufficient
- Include 1 to 5 predictions"""


# ---------------------------------------------------------------------------
# Bug explanation
# ---------------------------------------------------------------------------

EXPLANATION_SYSTEM = """You are a software debugger. Explain the bug clearly.
You MUST respond ONLY with a JSON object."""

EXPLANATION_USER = """Bug report: {issue_text}

Bug location:
File: {file}
Function: {function}
Lines: {line_start}-{line_end}

Source code:
{source_code}

Affected files/functions: {affected}

Return this JSON:
{{
  "what_is_wrong": "Describe the bug",
  "why_is_it_wrong": "Explain why this code is wrong",
  "what_should_happen": "Describe the correct behavior",
  "what_actually_happens": "Describe what happens instead",
  "downstream_impact": "What else does this break",
  "root_cause": {{
    "file": "path/to/file.py",
    "function": "function_name",
    "line_start": 10,
    "line_end": 20,
    "explanation": "Root cause explanation"
  }},
  "affected_components": [
    {{"file": "path/to/file.py", "function": "function_name", "how_affected": "How it is affected"}}
  ],
  "dependency_chain": ["step1 causes step2 causes step3"]
}}"""


# ---------------------------------------------------------------------------
# Fix generation
# ---------------------------------------------------------------------------

FIX_SYSTEM = """You are a software engineer creating minimal bug fixes.
Make only the smallest change needed to fix the bug.
You MUST respond ONLY with a JSON object."""

FIX_USER = """Bug report: {issue_text}

Bug location:
File: {file}
Function: {function}
Lines: {line_start}-{line_end}

Current code:
{current_code}

Bug explanation: {explanation}

Return this JSON:
{{
  "proposed_code": "Complete corrected function code here",
  "diff_description": "Brief description of what changed",
  "changed_lines": ["line X: old value -> new value"],
  "why_this_fixes": "Why this fix addresses the bug",
  "why_safe": "Why this change is safe",
  "potential_side_effects": "Any possible side effects",
  "is_minimal": true
}}"""
