"""code_review — static heuristic analysis of a source file.

Detects common code smells and issues without running a linter, so it works
even when the project environment is not fully installed.  The agent can use
this to highlight areas worth investigating before suggesting edits.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List


# ── Heuristic rule definitions ────────────────────────────────────────────────

_RULES = {
    "todo_fixme": (
        re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b", re.IGNORECASE),
        "Unresolved annotation",
        "low",
    ),
    "hardcoded_secret": (
        re.compile(
            r'(?i)(password|secret|api_key|token|passwd)\s*=\s*["\'][^"\']{4,}["\']'
        ),
        "Possible hardcoded credential",
        "high",
    ),
    "bare_except": (
        re.compile(r"^\s*except\s*:", re.MULTILINE),
        "Bare except clause swallows all exceptions",
        "medium",
    ),
    "print_statement": (
        re.compile(r"^\s*print\(", re.MULTILINE),
        "Debug print() left in production code",
        "low",
    ),
    "long_line": (
        None,  # handled separately
        "Line exceeds 120 characters",
        "low",
    ),
}


def code_review(
    path: str,
    *,
    max_function_lines: int = 60,
    max_line_length: int = 120,
) -> Dict[str, Any]:
    """Review *path* for common code smells and return structured findings.

    Args:
        path: Path to the source file to review.
        max_function_lines: Flag functions longer than this many lines.
        max_line_length: Flag lines longer than this many characters.

    Returns:
        dict with keys:
          - ``file``: path reviewed
          - ``language``: detected language
          - ``findings``: list of dicts with ``rule``, ``severity``, ``line``, ``message``
          - ``stats``: dict with ``lines``, ``functions``, ``classes``, ``complexity_warnings``
          - ``ok``: True if no high-severity findings
    """
    file_path = Path(path)
    if not file_path.exists():
        return {"file": path, "ok": False, "error": f"File not found: {path}"}

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"file": path, "ok": False, "error": str(exc)}

    language = _detect_language(file_path)
    lines = source.splitlines()
    findings: List[Dict[str, Any]] = []

    # ── Regex-based rules ─────────────────────────────────────────────────────
    for rule_name, (pattern, message, severity) in _RULES.items():
        if rule_name == "long_line":
            for lineno, line in enumerate(lines, start=1):
                if len(line) > max_line_length:
                    findings.append({
                        "rule": "long_line",
                        "severity": "low",
                        "line": lineno,
                        "message": f"Line length {len(line)} > {max_line_length}",
                        "snippet": line.strip()[:80],
                    })
            continue

        for m in pattern.finditer(source):
            lineno = source[: m.start()].count("\n") + 1
            findings.append({
                "rule": rule_name,
                "severity": severity,
                "line": lineno,
                "message": message,
                "snippet": lines[lineno - 1].strip()[:100] if lineno <= len(lines) else "",
            })

    # ── Python AST analysis ───────────────────────────────────────────────────
    stats: Dict[str, Any] = {
        "lines": len(lines),
        "functions": 0,
        "classes": 0,
        "complexity_warnings": 0,
    }

    if language == "python":
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            findings.append({
                "rule": "syntax_error",
                "severity": "high",
                "line": getattr(exc, "lineno", None),
                "message": f"Syntax error: {exc.msg}",
                "snippet": str(exc.text or "").strip(),
            })
            tree = None

        if tree:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    stats["functions"] += 1
                    fn_lines = (node.end_lineno or node.lineno) - node.lineno
                    if fn_lines > max_function_lines:
                        stats["complexity_warnings"] += 1
                        findings.append({
                            "rule": "long_function",
                            "severity": "medium",
                            "line": node.lineno,
                            "message": (
                                f"Function '{node.name}' is {fn_lines} lines "
                                f"(threshold: {max_function_lines})"
                            ),
                            "snippet": f"def {node.name}(...)",
                        })
                elif isinstance(node, ast.ClassDef):
                    stats["classes"] += 1

    has_high = any(f["severity"] == "high" for f in findings)
    return {
        "file": path,
        "language": language,
        "findings": findings,
        "stats": stats,
        "ok": not has_high,
    }


def _detect_language(path: Path) -> str:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".go": "go",
        ".java": "java", ".rs": "rust", ".c": "c", ".cpp": "cpp",
        ".sh": "shell", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".md": "markdown",
    }
    return ext_map.get(path.suffix.lower(), "unknown")
