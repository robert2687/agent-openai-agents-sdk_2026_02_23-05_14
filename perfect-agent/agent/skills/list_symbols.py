"""list_symbols - basic symbol extraction from source files."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List


_JS_FUNC_RE = re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_JS_CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_JS_EXPORT_RE = re.compile(r"\bexport\s+(?:default\s+)?(?:function|class|const|let|var)?\s*([A-Za-z_][A-Za-z0-9_]*)?")


def list_symbols(path: str) -> Dict[str, Any]:
    """Return discovered symbols (functions/classes/imports/exports) for a file."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": f"File not found: {path}"}

    try:
        source = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    ext = p.suffix.lower()
    if ext == ".py":
        return _python_symbols(path, source)
    if ext in {".js", ".jsx", ".ts", ".tsx"}:
        return _js_symbols(path, source)

    return {"ok": False, "error": f"Unsupported file type: {ext}"}


def _python_symbols(path: str, source: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"ok": False, "error": f"Syntax error: {exc.msg}", "line": exc.lineno}

    functions: List[str] = []
    classes: List[str] = []
    imports: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.extend(f"{mod}.{alias.name}" if mod else alias.name for alias in node.names)

    return {
        "ok": True,
        "path": path,
        "language": "python",
        "functions": sorted(set(functions)),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
    }


def _js_symbols(path: str, source: str) -> Dict[str, Any]:
    functions = sorted(set(m.group(1) for m in _JS_FUNC_RE.finditer(source)))
    classes = sorted(set(m.group(1) for m in _JS_CLASS_RE.finditer(source)))
    exports = sorted(set((m.group(1) or "default") for m in _JS_EXPORT_RE.finditer(source)))

    return {
        "ok": True,
        "path": path,
        "language": "javascript_or_typescript",
        "functions": functions,
        "classes": classes,
        "exports": exports,
    }
