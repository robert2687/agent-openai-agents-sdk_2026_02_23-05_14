"""git_ops — structured Git operations via the CLI.

Exposes a single ``git_ops(action, ...)`` function the agent can call for
common read and write operations without needing to craft raw shell commands.
"""
from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional


def _run(args: List[str], cwd: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except FileNotFoundError:
        return {"ok": False, "error": "git not found in PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git command timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def git_ops(
    action: str,
    path: str = ".",
    *,
    message: Optional[str] = None,
    files: Optional[List[str]] = None,
    remote: str = "origin",
    branch: Optional[str] = None,
    n: int = 10,
) -> Dict[str, Any]:
    """Perform a Git operation.

    Args:
        action: One of ``status``, ``diff``, ``log``, ``add``, ``commit``,
                ``push``, ``pull``, ``branch``, ``stash``.
        path: Repository root directory (default ``"."``).
        message: Commit message (required for ``commit``).
        files: List of file paths for ``add`` (default all staged files).
        remote: Remote name for ``push``/``pull`` (default ``"origin"``).
        branch: Branch name for ``push``/``pull``/``branch`` operations.
        n: Number of log entries to return (default 10).

    Returns:
        dict with ``ok``, ``stdout``, ``stderr``, and optionally ``error``.
    """
    a = action.lower().strip()

    if a == "status":
        return _run(["git", "status", "--short"], cwd=path)

    if a == "diff":
        return _run(["git", "diff", "--stat", "HEAD"], cwd=path)

    if a == "log":
        fmt = "--pretty=format:%h %ad %an: %s"
        return _run(["git", "log", fmt, "--date=short", f"-{n}"], cwd=path)

    if a == "add":
        targets = files if files else ["."]
        return _run(["git", "add", "--"] + targets, cwd=path)

    if a == "commit":
        if not message:
            return {"ok": False, "error": "commit requires a 'message' argument"}
        return _run(["git", "commit", "-m", message], cwd=path)

    if a == "push":
        cmd = ["git", "push", remote]
        if branch:
            cmd.append(branch)
        return _run(cmd, cwd=path)

    if a == "pull":
        cmd = ["git", "pull", remote]
        if branch:
            cmd.append(branch)
        return _run(cmd, cwd=path)

    if a == "branch":
        if branch:
            return _run(["git", "checkout", "-b", branch], cwd=path)
        return _run(["git", "branch", "--list"], cwd=path)

    if a == "stash":
        return _run(["git", "stash"], cwd=path)

    return {"ok": False, "error": f"Unknown git action: '{action}'. "
            "Choose from: status, diff, log, add, commit, push, pull, branch, stash"}
