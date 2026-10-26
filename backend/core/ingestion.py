"""
Repository ingestion: clone, record commit, scan files.
Security: treats all repository content as untrusted.
Never executes repository code during ingestion.
"""
from __future__ import annotations
import hashlib
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import List, Optional

import git
from git import Repo, GitCommandError

from config.settings import settings

logger = logging.getLogger(__name__)

# Directories to always exclude from scanning
IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "coverage", ".mypy_cache", ".pytest_cache",
    ".tox", "htmlcov", "*.egg-info",
}

# File extensions to scan per language
LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py"],
    "javascript": [".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "go": [".go"],
    "rust": [".rs"],
}


def _validate_github_url(url: str) -> bool:
    """Basic GitHub URL validation. Accepts https:// only."""
    pattern = r'^https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?$'
    return bool(re.match(pattern, url.strip()))


def _detect_language(repo_path: Path) -> str:
    """
    Detect primary programming language by counting source files.
    JS and TS are merged into 'javascript' since we use the same parser.
    Returns the language name or 'unknown'.
    """
    counts: dict[str, int] = {}
    # Check Python
    counts["python"] = len(list(repo_path.rglob("*.py")))
    # Check JS/TS combined
    js_count = sum(
        len(list(repo_path.rglob(f"*{ext}")))
        for ext in [".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"]
    )
    counts["javascript"] = js_count
    counts["java"] = len(list(repo_path.rglob("*.java")))
    counts["go"] = len(list(repo_path.rglob("*.go")))
    counts["rust"] = len(list(repo_path.rglob("*.rs")))

    # Filter zeros
    counts = {k: v for k, v in counts.items() if v > 0}
    if not counts:
        return "unknown"
    return max(counts, key=lambda k: counts[k])


def _is_ground_truth_path(path: Path, exclusions: List[str]) -> bool:
    """
    Return True if the path matches any ground-truth exclusion pattern.
    Ground-truth files must never be read during localization.
    """
    path_str = str(path)
    for exclusion in exclusions:
        if exclusion in path_str:
            return True
    return False


def clone_repository(url: str) -> tuple[str, str]:
    """
    Clone a GitHub repository into an isolated workspace directory.

    Returns:
        (local_path, commit_hash)

    Raises:
        ValueError: on invalid URL or clone failure
    """
    if not _validate_github_url(url):
        raise ValueError(f"Invalid or non-GitHub URL: {url!r}. Only https://github.com/... URLs are accepted.")

    # Create unique directory per clone
    repo_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:12]
    target = settings.workspace_path / repo_id

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    logger.info("Cloning %s → %s", url, target)
    try:
        repo = Repo.clone_from(
            url,
            str(target),
            no_checkout=False,
            depth=1,               # shallow clone for speed
        )
        commit_hash = repo.head.commit.hexsha
        logger.info("Cloned. Commit: %s", commit_hash)
        return str(target), commit_hash
    except GitCommandError as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise ValueError(f"Failed to clone repository: {exc}") from exc


def scan_source_files(
    repo_path: str,
    language: str,
    ground_truth_exclusions: Optional[List[str]] = None,
) -> List[Path]:
    """
    Scan the repository for source files of the detected language.
    Excludes ground-truth files, ignored directories, and test-evaluation files.

    Returns list of absolute Paths.
    """
    exclusions = ground_truth_exclusions or settings.ground_truth_exclusion_list
    root = Path(repo_path)

    # javascript covers both JS and TS files
    if language == "javascript":
        extensions = [".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"]
    else:
        extensions = LANGUAGE_EXTENSIONS.get(language, [])

    if not extensions:
        logger.warning("No known extensions for language: %s", language)
        return []

    results: List[Path] = []
    for ext in extensions:
        for path in root.rglob(f"*{ext}"):
            # Skip ignored directories
            parts = set(path.relative_to(root).parts)
            if parts & IGNORED_DIRS:
                continue
            # Skip ground-truth paths
            if _is_ground_truth_path(path, exclusions):
                logger.debug("Skipping ground-truth file: %s", path)
                continue
            results.append(path)

    logger.info("Found %d source files (%s)", len(results), language)
    return sorted(results)
