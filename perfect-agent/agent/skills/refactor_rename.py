"""refactor_rename — safe identifier rename across a codebase with preview mode."""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path
from typing import Any, Dict, List

_DEFAULT_EXTENSIONS = {".py", ".ts", ".js", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs"}


def _rename_python(source: str, regex: re.Pattern[str], new_name: str) -> str:
    """Replace names while preserving Python comments and string literals."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (IndentationError, tokenize.TokenError):
        return source
    return tokenize.untokenize(
        token._replace(string=regex.sub(new_name, token.string))
        if token.type == tokenize.NAME else token
        for token in tokens
    )


def _rename_code(source: str, regex: re.Pattern[str], new_name: str, *, hash_comments: bool) -> str:
    """Replace code outside quoted strings and line/block comments."""
    result: List[str] = []
    code_start = 0
    index = 0
    length = len(source)

    while index < length:
        quote = source[index]
        line_comment = source.startswith("//", index) or (hash_comments and quote == "#")
        block_comment = source.startswith("/*", index)
        if quote not in "'\"`" and not line_comment and not block_comment:
            index += 1
            continue

        result.append(regex.sub(new_name, source[code_start:index]))
        start = index
        if line_comment:
            newline = source.find("\n", index)
            index = length if newline < 0 else newline
        elif block_comment:
            end = source.find("*/", index + 2)
            index = length if end < 0 else end + 2
        else:
            index += 1
            while index < length:
                if source[index] == "\\":
                    index += 2
                elif source[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
        result.append(source[start:index])
        code_start = index

    result.append(regex.sub(new_name, source[code_start:]))
    return "".join(result)


def _rename_source(source: str, suffix: str, regex: re.Pattern[str], new_name: str) -> str:
    if suffix == ".py":
        return _rename_python(source, regex, new_name)
    return _rename_code(source, regex, new_name, hash_comments=suffix == ".rb")


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
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        updated = _rename_source(source, file_path.suffix, regex, new_name)
        if updated != source:
            old_lines = source.splitlines()
            new_lines = updated.splitlines()
            for lineno, (line, new_line) in enumerate(zip(old_lines, new_lines), start=1):
                if new_line != line:
                    changes.append({
                        "file": str(file_path),
                        "line": lineno,
                        "before": line,
                        "after": new_line,
                    })
            files_with_changes.append(file_path)
            if not dry_run:
                file_path.write_text(updated, encoding="utf-8")

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
