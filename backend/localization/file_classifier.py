"""
Generic file classifier for distinguishing production source code from
test/auxiliary files.

Rules are purely pattern-based — no hard-coded repository-specific paths.
Works generically for any Python, JavaScript, or TypeScript repository.
"""
from __future__ import annotations
import re
from pathlib import Path

# ── Path-segment patterns that indicate a test/auxiliary file ───────────────
TEST_PATH_PATTERNS = re.compile(
    r"""
    (^|/)test(s)?(/|$)          # /test/ or /tests/ directory
    | (^|/)spec(s)?(/|$)        # /spec/ or /specs/ directory
    | (^|/)__tests__(/|$)       # Jest __tests__
    | (^|/)reproduction_tests?(/|$)  # reproduction_tests/
    | (^|/)benchmark(s)?(/|$)   # benchmarks
    | (^|/)fixtures?(/|$)       # fixtures
    | (^|/)mocks?(/|$)          # mocks
    | (^|/)stubs?(/|$)          # stubs
    | (^|/)conftest             # conftest.py (pytest fixture)
    | (^|/)setup\.cfg$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── Filename-level patterns ──────────────────────────────────────────────────
TEST_FILE_PATTERNS = re.compile(
    r"""
    ^test_          # test_*.py  (pytest convention)
    | _test\.(py|js|ts|jsx|tsx)$   # *_test.py / *_test.js
    | \.test\.(js|ts|jsx|tsx)$     # *.test.js  (Jest)
    | \.spec\.(js|ts|jsx|tsx)$     # *.spec.ts  (Jest/Mocha)
    | ^conftest\.py$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── Dataset / metadata file patterns ────────────────────────────────────────
METADATA_FILE_PATTERNS = re.compile(
    r"""
    BUG_DATASET
    | bug_dataset
    | ground_truth
    | dataset
    | corrected_patch
    | evaluation
    | README
    | CHANGELOG
    | CONTRIBUTING
    | LICENSE
    """,
    re.VERBOSE | re.IGNORECASE,
)


def is_test_file(file_path: str) -> bool:
    """
    Return True if the file path looks like a test/spec/fixture/mock file.
    Generic — works for any repository layout without hard-coding paths.
    """
    # Normalise separators
    normed = file_path.replace("\\", "/")
    filename = Path(normed).name

    if TEST_PATH_PATTERNS.search(normed):
        return True
    if TEST_FILE_PATTERNS.search(filename):
        return True
    return False


def is_metadata_file(file_path: str) -> bool:
    """Return True if the file is a dataset / documentation / metadata file."""
    filename = Path(file_path.replace("\\", "/")).name
    return bool(METADATA_FILE_PATTERNS.search(filename))


def is_source_file(file_path: str) -> bool:
    """Return True iff the file is production source code (not test, not metadata)."""
    return not is_test_file(file_path) and not is_metadata_file(file_path)


def classify_file(file_path: str) -> str:
    """Return 'source', 'test', or 'metadata'."""
    if is_metadata_file(file_path):
        return "metadata"
    if is_test_file(file_path):
        return "test"
    return "source"
