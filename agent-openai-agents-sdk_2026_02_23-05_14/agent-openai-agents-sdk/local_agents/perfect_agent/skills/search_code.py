"""search_code — recursive regex/literal search across a directory tree.

Returns up to ``max_results`` matches as ``file:line:snippet`` strings so the
agent can pinpoint where a symbol, pattern, or keyword lives without reading
every file individually.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".md", ".txt", ".toml", ".cfg", ".ini", ".sh", ".html", ".css",
    ".env", ".tf", ".go", ".java", ".rs", ".c", ".cpp", ".h",
}


def search_code(
    pattern: str,
    root: str = ".",
    *,
    is_regex: bool = False,
    case_sensitive: bool = False,
    include_extensions: Optional[List[str]] = None,
    max_results: int = 50,
) -> Dict[str, Any]:
    """Search for *pattern* in every text file under *root*.

    Args:
        pattern: Literal string or regex to search for.
        root: Directory to search recursively (default current dir).
        is_regex: Treat *pattern* as a regular expression.
        case_sensitive: Case-sensitive match (default False).
        include_extensions: If given, only search files with these extensions
            (e.g. [".py", ".ts"]).
        max_results: Cap on the number of matches returned.

    Returns:
        dict with keys:
          - ``matches``: list of "path:lineno: snippet" strings
          - ``total``: total matches found (may exceed max_results)
          - ``truncated``: True if results were capped
    """
    root_path = Path(root).resolve()
    if not root_path.exists():
        return {"matches": [], "total": 0, "truncated": False, "error": f"Path not found: {root}"}

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern if is_regex else re.escape(pattern), flags)
    except re.error as exc:
        return {"matches": [], "total": 0, "truncated": False, "error": f"Invalid regex: {exc}"}

    allowed_exts = set(include_extensions) if include_extensions else _TEXT_EXTENSIONS
    matches: List[str] = []
    total = 0
    truncated = False

    for file_path in sorted(root_path.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in allowed_exts:
            continue
        # Skip hidden dirs and common noise dirs
        if any(part.startswith(".") or part in {"__pycache__", "node_modules", ".venv", "dist", "build"}
               for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            if compiled.search(line):
                total += 1
                if len(matches) < max_results:
                    rel = file_path.relative_to(root_path)
                    matches.append(f"{rel}:{lineno}: {line.strip()[:120]}")
                else:
                    truncated = True

    return {"matches": matches, "total": total, "truncated": truncated}
