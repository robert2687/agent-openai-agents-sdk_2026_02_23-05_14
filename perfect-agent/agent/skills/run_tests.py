"""run_tests — discover and execute the test suite, return structured results.

Runs ``pytest`` (preferred) or ``unittest discover`` and parses the summary
so the agent can reason about failures without reading raw terminal output.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_tests(
    root: str = ".",
    *,
    pattern: str = "test_*.py",
    extra_args: Optional[List[str]] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Run the project's test suite and return a structured summary.

    Tries ``pytest`` first; falls back to ``python -m unittest discover``.

    Args:
        root: Directory to run tests in (default ``"."``).
        pattern: Test file glob pattern (used by unittest discover).
        extra_args: Additional CLI args forwarded to pytest (e.g. ["-k", "auth"]).
        timeout: Max seconds to wait for the test run.

    Returns:
        dict with keys:
          - ``ok``: True if all tests passed
          - ``runner``: "pytest" or "unittest"
          - ``passed``, ``failed``, ``errors``, ``skipped``: counts (where available)
          - ``summary``: last few lines of output
          - ``failures``: list of failure snippets (pytest only)
          - ``stdout``, ``stderr``: full output
    """
    cwd = str(Path(root).resolve())
    extra = extra_args or []

    # ── Try pytest ────────────────────────────────────────────────────────────
    pytest_cmd = ["python", "-m", "pytest", "--tb=short", "-q"] + extra
    try:
        result = subprocess.run(
            pytest_cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        if result.returncode not in (4, 5):  # 4 = no tests collected is still valid
            return _parse_pytest(result)
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        return {"ok": False, "runner": "pytest", "error": "Timed out", "summary": "Test run timed out"}

    # ── Fallback: unittest discover ───────────────────────────────────────────
    unittest_cmd = [
        "python", "-m", "unittest", "discover",
        "-s", cwd, "-p", pattern,
    ]
    try:
        result = subprocess.run(
            unittest_cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return _parse_unittest(result)
    except subprocess.TimeoutExpired:
        return {"ok": False, "runner": "unittest", "error": "Timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "runner": "unknown", "error": str(exc)}


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_pytest(result: subprocess.CompletedProcess) -> Dict[str, Any]:
    stdout = result.stdout
    stderr = result.stderr
    out = {}

    # e.g. "3 passed, 1 failed, 2 warnings in 0.45s"
    summary_match = re.search(
        r"(\d+) passed(?:,\s*(\d+) failed)?(?:,\s*(\d+) error)?(?:,\s*(\d+) skipped)?",
        stdout,
    )
    if summary_match:
        out["passed"] = int(summary_match.group(1) or 0)
        out["failed"] = int(summary_match.group(2) or 0)
        out["errors"] = int(summary_match.group(3) or 0)
        out["skipped"] = int(summary_match.group(4) or 0)
    else:
        out["passed"] = out["failed"] = out["errors"] = out["skipped"] = None

    # Extract FAILED lines
    failures: List[str] = re.findall(r"^FAILED .+", stdout, re.MULTILINE)

    lines = stdout.strip().splitlines()
    summary = "\n".join(lines[-15:]) if lines else ""

    return {
        "ok": result.returncode == 0,
        "runner": "pytest",
        **out,
        "failures": failures,
        "summary": summary,
        "stdout": stdout,
        "stderr": stderr,
    }


def _parse_unittest(result: subprocess.CompletedProcess) -> Dict[str, Any]:
    stderr = result.stderr  # unittest writes to stderr
    ran_match = re.search(r"Ran (\d+) test", stderr)
    ok_match = re.search(r"^(OK|FAILED)", stderr, re.MULTILINE)
    fail_match = re.search(r"failures=(\d+)", stderr)
    err_match = re.search(r"errors=(\d+)", stderr)

    return {
        "ok": result.returncode == 0,
        "runner": "unittest",
        "passed": int(ran_match.group(1)) if ran_match else None,
        "failed": int(fail_match.group(1)) if fail_match else 0,
        "errors": int(err_match.group(1)) if err_match else 0,
        "skipped": None,
        "failures": [],
        "summary": stderr.strip()[-800:],
        "stdout": result.stdout,
        "stderr": stderr,
    }
