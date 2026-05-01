"""format_code — run a code formatter on a source file and return the result."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


_FORMATTERS: Dict[str, Dict[str, Any]] = {
    "black": {
        "extensions": {".py"},
        "cmd": [sys.executable, "-m", "black", "--quiet", "{path}"],
    },
    "autopep8": {
        "extensions": {".py"},
        "cmd": [sys.executable, "-m", "autopep8", "--in-place", "{path}"],
    },
    "prettier": {
        "extensions": {".js", ".ts", ".jsx", ".tsx", ".json", ".css", ".html", ".md"},
        "cmd": ["npx", "prettier", "--write", "{path}"],
    },
}


def format_code(
    path: str,
    *,
    formatter: str = "auto",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Format a source file using the appropriate formatter.

    Args:
        path: Path to the file to format.
        formatter: "auto" (pick by extension), "black", "autopep8", or "prettier".
        dry_run: If True, return the formatted content without writing to disk.

    Returns:
        dict with ``ok``, ``formatter_used``, ``changed`` (bool), and optionally
        ``content`` when dry_run is True.
    """
    file_path = Path(path)
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: {path}"}

    ext = file_path.suffix.lower()
    chosen = _pick_formatter(formatter, ext)
    if chosen is None:
        return {
            "ok": False,
            "error": f"No formatter available for extension '{ext}'. "
                     f"Supported: {list(_FORMATTERS)}",
        }

    original = file_path.read_bytes()

    if dry_run:
        formatted = _run_formatter_stdout(chosen, file_path)
        if formatted is None:
            return {"ok": False, "error": "Formatter failed or dry-run not supported."}
        changed = formatted.encode() != original
        return {
            "ok": True,
            "formatter_used": chosen,
            "dry_run": True,
            "changed": changed,
            "content": formatted,
        }

    result = _run_formatter_inplace(chosen, file_path)
    if not result["success"]:
        return {"ok": False, "error": result.get("stderr", "Formatter failed.")}

    new_content = file_path.read_bytes()
    changed = new_content != original
    return {"ok": True, "formatter_used": chosen, "dry_run": False, "changed": changed}


# ── Internals ─────────────────────────────────────────────────────────────────

def _pick_formatter(formatter: str, ext: str) -> str | None:
    if formatter != "auto":
        return formatter if formatter in _FORMATTERS else None
    for name, meta in _FORMATTERS.items():
        if ext in meta["extensions"]:
            return name
    return None


def _build_cmd(formatter: str, file_path: Path) -> list[str]:
    tmpl = _FORMATTERS[formatter]["cmd"]
    return [part.replace("{path}", str(file_path)) for part in tmpl]


def _run_formatter_inplace(formatter: str, file_path: Path) -> Dict[str, Any]:
    cmd = _build_cmd(formatter, file_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError:
        return {"success": False, "stderr": f"Formatter '{formatter}' not found in PATH."}
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": "Formatter timed out."}


def _run_formatter_stdout(formatter: str, file_path: Path) -> str | None:
    """Attempt to get formatted output on stdout (black --check workaround)."""
    if formatter == "black":
        cmd = [sys.executable, "-m", "black", "--quiet", "--diff", str(file_path)]
    elif formatter == "prettier":
        cmd = ["npx", "prettier", str(file_path)]
    else:
        # autopep8 supports stdout mode
        cmd = [sys.executable, "-m", "autopep8", str(file_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return proc.stdout if proc.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
