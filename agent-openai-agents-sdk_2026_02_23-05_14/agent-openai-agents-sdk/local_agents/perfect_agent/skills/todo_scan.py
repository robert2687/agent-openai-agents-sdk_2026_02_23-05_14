"""todo_scan - locate TODO/FIXME/HACK markers in a codebase."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|BUG|XXX)\b", re.IGNORECASE)
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}


def todo_scan(root: str = ".", *, max_results: int = 100) -> Dict[str, Any]:
    """Scan files under root for TODO-like markers.

    Returns a structured list of marker hits with path and line information.
    """
    root_path = Path(root).resolve()
    if not root_path.exists():
        return {"ok": False, "error": f"Path not found: {root}", "items": []}

    items: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {"TODO": 0, "FIXME": 0, "HACK": 0, "BUG": 0, "XXX": 0}

    for p in sorted(root_path.rglob("*")):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS or part.startswith(".") for part in p.parts):
            continue

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _MARKER_RE.search(line)
            if not m:
                continue
            marker = m.group(1).upper()
            counts[marker] = counts.get(marker, 0) + 1

            if len(items) < max_results:
                items.append(
                    {
                        "path": str(p.relative_to(root_path)),
                        "line": lineno,
                        "marker": marker,
                        "text": line.strip()[:160],
                    }
                )

    total = sum(counts.values())
    return {
        "ok": True,
        "root": str(root_path),
        "total": total,
        "counts": counts,
        "items": items,
        "truncated": total > len(items),
    }
