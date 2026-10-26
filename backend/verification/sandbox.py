"""
Docker-based fix verification sandbox.

Security guarantees:
  - Repository code is NEVER executed on the host.
  - A temporary copy of the repository is created.
  - The proposed patch is applied to the copy.
  - Tests run inside an isolated Docker container.
  - The original repository is never modified.
  - Network access is disabled in the container.
  - Container is always removed after use.
"""
from __future__ import annotations
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from core.models import (
    ProposedFix,
    VerificationResult,
    VerificationStatus,
    TestResult,
)
from config.settings import settings

logger = logging.getLogger(__name__)


def _docker_available() -> bool:
    """Check if Docker is installed and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _apply_patch(
    repo_path: str,
    fix: ProposedFix,
) -> Tuple[bool, str]:
    """
    Apply the proposed fix to a copy of the repository.
    Replaces the current function source code with the proposed code.

    Returns (success, error_message).
    """
    target_file = Path(repo_path) / fix.file
    if not target_file.exists():
        return False, f"Target file not found: {fix.file}"

    try:
        original_content = target_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"Cannot read target file: {exc}"

    # Replace current function code with proposed code
    # Use exact string replacement on the function body
    current = fix.current_code.strip()
    proposed = fix.proposed_code.strip()

    if current not in original_content:
        # Try with normalized whitespace
        logger.warning("Exact match failed, trying normalized replacement.")
        # Attempt line-by-line replacement
        return False, "Could not locate the current function code in the file for patching."

    patched_content = original_content.replace(current, proposed, 1)

    try:
        target_file.write_text(patched_content, encoding="utf-8")
        return True, ""
    except OSError as exc:
        return False, f"Cannot write patched file: {exc}"


def _parse_pytest_output(output: str) -> List[TestResult]:
    """Parse pytest stdout into TestResult objects."""
    results = []
    # Match pytest result lines like: "PASSED tests/test_foo.py::test_bar"
    for line in output.splitlines():
        line = line.strip()
        for status in ("PASSED", "FAILED", "ERROR", "SKIPPED"):
            if line.startswith(status):
                name = line[len(status):].strip()
                results.append(TestResult(name=name, status=status))
                break
    return results


def _extract_summary(output: str) -> Tuple[int, int]:
    """Extract (passed, failed) counts from pytest summary line."""
    # "3 passed, 1 failed" or "2 passed"
    passed = 0
    failed = 0
    match = re.search(r'(\d+) passed', output)
    if match:
        passed = int(match.group(1))
    match = re.search(r'(\d+) failed', output)
    if match:
        failed = int(match.group(1))
    return passed, failed


class VerificationSandbox:
    """
    Verifies a proposed fix using an isolated Docker container.

    The sandbox:
    1. Creates a temporary copy of the repo.
    2. Applies the patch to the copy.
    3. Runs tests before the patch (baseline).
    4. Applies the patch.
    5. Runs tests after the patch.
    6. Returns structured results.
    """

    def verify(
        self,
        repo_path: str,
        fix: ProposedFix,
        language: str = "python",
    ) -> VerificationResult:
        if not settings.enable_docker_verification:
            return VerificationResult(
                status=VerificationStatus.UNAVAILABLE,
                notes="Docker verification is disabled in configuration.",
                docker_used=False,
            )

        if not _docker_available():
            return VerificationResult(
                status=VerificationStatus.UNAVAILABLE,
                notes="Docker is not available on this system. Install Docker to enable verification.",
                docker_used=False,
            )

        # Detect test framework
        test_cmd = self._detect_test_command(repo_path, language)
        if not test_cmd:
            return VerificationResult(
                status=VerificationStatus.UNAVAILABLE,
                notes="No supported test framework detected (pytest, unittest). Cannot verify.",
                docker_used=True,
            )

        temp_dir = None
        try:
            # Create isolated temporary copy
            temp_dir = tempfile.mkdtemp(prefix="buglocalizer_verify_")
            temp_repo = Path(temp_dir) / "repo"
            shutil.copytree(repo_path, str(temp_repo), symlinks=False)

            # Run tests BEFORE applying the patch
            before_output, before_rc = self._run_tests_in_docker(str(temp_repo), test_cmd)
            tests_before = _parse_pytest_output(before_output)
            passed_before, failed_before = _extract_summary(before_output)

            # Apply the patch
            success, patch_error = _apply_patch(str(temp_repo), fix)
            if not success:
                return VerificationResult(
                    status=VerificationStatus.UNAVAILABLE,
                    notes=f"Could not apply patch: {patch_error}",
                    tests_before=tests_before,
                    passed_before=passed_before,
                    failed_before=failed_before,
                    docker_used=True,
                )

            # Run tests AFTER applying the patch
            after_output, after_rc = self._run_tests_in_docker(str(temp_repo), test_cmd)
            tests_after = _parse_pytest_output(after_output)
            passed_after, failed_after = _extract_summary(after_output)

            # Determine verification status
            status = self._determine_status(
                before_rc, after_rc, passed_before, failed_before, passed_after, failed_after
            )

            reproduction_before = "FAILED" if failed_before > 0 else "PASSED"
            reproduction_after = "PASSED" if after_rc == 0 and failed_after == 0 else "FAILED"

            return VerificationResult(
                status=status,
                reproduction_test_before=reproduction_before,
                reproduction_test_after=reproduction_after,
                tests_before=tests_before,
                tests_after=tests_after,
                passed_before=passed_before,
                failed_before=failed_before,
                passed_after=passed_after,
                failed_after=failed_after,
                notes=f"Verified using Docker. Test command: {test_cmd}",
                docker_used=True,
            )

        except Exception as exc:
            logger.error("Verification failed with exception: %s", exc)
            return VerificationResult(
                status=VerificationStatus.UNAVAILABLE,
                notes=f"Verification error: {exc}",
                docker_used=True,
            )
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _detect_test_command(self, repo_path: str, language: str) -> Optional[str]:
        """Detect the test runner command for the repository."""
        root = Path(repo_path)
        if language == "python":
            if (root / "pytest.ini").exists() or (root / "setup.cfg").exists() or (root / "pyproject.toml").exists():
                return "python -m pytest -v --tb=short"
            if any(root.rglob("test_*.py")) or any(root.rglob("*_test.py")):
                return "python -m pytest -v --tb=short"
        return None

    def _run_tests_in_docker(
        self,
        repo_path: str,
        test_cmd: str,
    ) -> Tuple[str, int]:
        """
        Run tests inside an isolated Docker container.

        Security:
        - No network access (--network none)
        - Read-only host filesystem (repo mounted read-write only for temp copy)
        - Resource limits applied
        - Container removed after run
        - Never mounts host filesystem secrets
        """
        container_name = f"buglocalizer_{uuid.uuid4().hex[:8]}"
        docker_cmd = [
            "docker", "run",
            "--rm",
            "--name", container_name,
            "--network", "none",                      # No network access
            "--memory", "512m",                       # Memory limit
            "--cpus", "1.0",                          # CPU limit
            "--read-only",                            # Read-only container FS
            "--tmpfs", "/tmp:size=100m",              # Writable tmp
            "--tmpfs", "/root/.cache:size=200m",      # pip cache
            "-v", f"{repo_path}:/repo:rw",            # Mount only the temp copy
            "-w", "/repo",
            "python:3.11-slim",
            "/bin/bash", "-c",
            f"pip install -q -r requirements.txt 2>/dev/null || true; {test_cmd}",
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=settings.docker_timeout_seconds,
            )
            output = result.stdout + "\n" + result.stderr
            return output, result.returncode
        except subprocess.TimeoutExpired:
            # Kill the container if it's still running
            subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True,
            )
            return "Verification timed out.", -1
        except Exception as exc:
            return f"Docker execution error: {exc}", -1

    @staticmethod
    def _determine_status(
        before_rc: int,
        after_rc: int,
        passed_before: int,
        failed_before: int,
        passed_after: int,
        failed_after: int,
    ) -> VerificationStatus:
        """Determine verification status from test results."""
        if after_rc == 0 and failed_after == 0:
            if failed_before > 0:
                return VerificationStatus.VERIFIED
            else:
                return VerificationStatus.PARTIALLY_VERIFIED  # No regression introduced
        elif failed_after < failed_before:
            return VerificationStatus.PARTIALLY_VERIFIED
        else:
            return VerificationStatus.NOT_VERIFIED
