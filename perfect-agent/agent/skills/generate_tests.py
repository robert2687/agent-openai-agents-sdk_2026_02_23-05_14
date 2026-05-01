"""generate_tests — generate pytest test stubs from a Python source file."""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import Any, Dict, List


def generate_tests(
    path: str,
    *,
    output_path: str = "",
    framework: str = "pytest",
) -> Dict[str, Any]:
    """Generate test stubs for all functions and methods found in a Python file.

    Args:
        path: Path to the source Python file to analyse.
        output_path: If given, write the generated stubs to this file path.
        framework: Testing framework — currently only "pytest" is supported.

    Returns:
        dict with keys: ``stubs`` (generated code string), ``symbols`` (list of
        function names stubs were created for), and optionally ``written`` (path).
    """
    src_path = Path(path)
    if not src_path.exists():
        return {"ok": False, "error": f"File not found: {path}"}
    if src_path.suffix not in {".py"}:
        return {"ok": False, "error": "Only Python files are supported."}

    try:
        source = src_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(src_path))
    except SyntaxError as exc:
        return {"ok": False, "error": f"Syntax error: {exc}"}

    symbols: List[str] = []
    stub_blocks: List[str] = []

    # Module-level imports header
    module_name = src_path.stem
    stub_blocks.append(
        f"\"\"\"Auto-generated test stubs for {src_path.name}.\"\"\"\n"
        f"import pytest\n"
        f"from {module_name} import *  # noqa: F401, F403\n"
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            methods = [
                n for n in ast.walk(node)
                if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
            ]
            if methods:
                stub_blocks.append(f"\n\nclass Test{class_name}:")
                for method in methods:
                    sym = f"{class_name}.{method.name}"
                    symbols.append(sym)
                    stub_blocks.append(_method_stub(method.name, class_name))
        elif isinstance(node, ast.FunctionDef):
            # Only top-level functions (parent is Module)
            if node.col_offset == 0 and not node.name.startswith("_"):
                symbols.append(node.name)
                stub_blocks.append(_function_stub(node.name))

    if not symbols:
        return {"ok": True, "stubs": "", "symbols": [], "message": "No public symbols found."}

    generated = "\n".join(stub_blocks) + "\n"

    result: Dict[str, Any] = {"ok": True, "stubs": generated, "symbols": symbols}

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(generated, encoding="utf-8")
        result["written"] = str(out)

    return result


def _function_stub(name: str) -> str:
    return textwrap.dedent(f"""

        def test_{name}():
            # TODO: implement test for {name}
            result = {name}()
            assert result is not None
    """)


def _method_stub(method_name: str, class_name: str) -> str:
    return textwrap.dedent(f"""
        def test_{method_name}(self):
            # TODO: implement test for {class_name}.{method_name}
            obj = {class_name}()
            result = obj.{method_name}()
            assert result is not None
    """)
