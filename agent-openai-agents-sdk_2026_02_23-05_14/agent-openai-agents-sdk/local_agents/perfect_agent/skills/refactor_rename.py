"""refactor_rename — safe identifier rename across a codebase with preview mode."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

_DEFAULT_EXTENSIONS = {".py", ".ts", ".js", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs"}


def refactor_rename(
    old_name: str,
    new_name: str,
    *,
    root: str = ".",
    whole_word: bool = True,
    dry_run: bool = True,
    include_extensions: List[str] | None = None,
    max_files: int = 200,
) -> Dict[str, Any]:
    """Rename an identifier across all matching source files.

    Args:
        old_name: The identifier to search for.
        new_name: The replacement identifier.
        root: Root directory to search (default '.').
        whole_word: Only match whole-word occurrences (default True, recommended).
        dry_run: If True (default), preview changes without writing to disk.
        include_extensions: File extensions to include; defaults to common source extensions.
        max_files: Maximum number of files to process.

    Returns:
        dict with ``changes`` list (file, line, before, after) and ``files_modified`` count.
    """
    if not old_name or not new_name:
        return {"ok": False, "error": "old_name and new_name are required."}
    if old_name == new_name:
        return {"ok": False, "error": "old_name and new_name are the same."}

    exts = set(include_extensions) if include_extensions else _DEFAULT_EXTENSIONS
    root_path = Path(root)
    if not root_path.is_dir():
        return {"ok": False, "error": f"Directory not found: {root}"}

    pattern_str = rf"\b{re.escape(old_name)}\b" if whole_word else re.escape(old_name)
    regex = re.compile(pattern_str)

    changes: List[Dict[str, Any]] = []
    files_with_changes: List[Path] = []
    files_checked = 0

    for file_path in sorted(root_path.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix not in exts:
            continue
        # Skip hidden directories
        if any(part.startswith(".") for part in file_path.parts):
            continue
        if files_checked >= max_files:
            break
        files_checked += 1

        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        new_lines: List[str] = []
        file_changed = False
        for lineno, line in enumerate(lines, start=1):
            new_line = regex.sub(new_name, line)
            if new_line != line:
                changes.append({
                    "file": str(file_path),
                    "line": lineno,
                    "before": line,
                    "after": new_line,
                })
                file_changed = True
            new_lines.append(new_line)

        if file_changed:
            files_with_changes.append(file_path)
            if not dry_run:
                file_path.write_text("\n".join(new_lines), encoding="utf-8")

    return {
        "ok": True,
        "dry_run": dry_run,
        "old_name": old_name,
        "new_name": new_name,
        "files_modified": len(files_with_changes),
        "total_occurrences": len(changes),
        "changes": changes[:100],  # cap preview at 100 entries
        "truncated": len(changes) > 100,
    }
