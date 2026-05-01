"""create_class — generate boilerplate class definition files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def create_class(
    name: str,
    *,
    language: str = "python",
    fields: List[str] | None = None,
    methods: List[str] | None = None,
    base_class: str = "",
    output_path: str = "",
) -> Dict[str, Any]:
    """Generate a boilerplate class file.

    Args:
        name: Class name (PascalCase recommended).
        language: "python", "typescript", or "java".
        fields: List of field names to include (e.g. ["id", "name", "email"]).
        methods: List of additional method names to stub (e.g. ["validate", "save"]).
        base_class: Optional parent class / interface to extend.
        output_path: If given, write the generated code to this file.

    Returns:
        dict with ``content`` (generated code) and optionally ``written``.
    """
    lang = language.strip().lower()
    fields = fields or []
    methods = methods or []

    generators = {
        "python": _python_class,
        "typescript": _typescript_class,
        "java": _java_class,
    }
    gen = generators.get(lang)
    if gen is None:
        return {"ok": False, "error": f"Unsupported language: {language}. Use python, typescript, or java."}

    content = gen(name, fields, methods, base_class)
    result: Dict[str, Any] = {"ok": True, "language": lang, "class_name": name, "content": content}

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        result["written"] = str(out)

    return result


# ── Generators ────────────────────────────────────────────────────────────────

def _python_class(name: str, fields: List[str], methods: List[str], base_class: str) -> str:
    inherits = f"({base_class})" if base_class else ""
    lines = [f"class {name}{inherits}:"]
    if fields:
        init_args = ", ".join(f"{f}: object = None" for f in fields)
        lines.append(f"    def __init__(self, {init_args}) -> None:")
        for f in fields:
            lines.append(f"        self.{f} = {f}")
    else:
        lines.append("    def __init__(self) -> None:")
        lines.append("        pass")

    lines.append("")
    lines.append("    def __repr__(self) -> str:")
    if fields:
        parts = ", ".join(f"{f}={{self.{f}!r}}" for f in fields)
        lines.append(f'        return f"{name}({parts})"')
    else:
        lines.append(f'        return "{name}()"')

    for method in methods:
        lines.append("")
        lines.append(f"    def {method}(self):")
        lines.append(f'        """TODO: implement {method}."""')
        lines.append("        raise NotImplementedError")

    return "\n".join(lines) + "\n"


def _typescript_class(name: str, fields: List[str], methods: List[str], base_class: str) -> str:
    extends = f" extends {base_class}" if base_class else ""
    lines = [f"export class {name}{extends} {{"]

    for f in fields:
        lines.append(f"  {f}: unknown;")

    if fields:
        lines.append("")
        ctor_params = ", ".join(f"{f}: unknown" for f in fields)
        lines.append(f"  constructor({ctor_params}) {{")
        for f in fields:
            lines.append(f"    this.{f} = {f};")
        lines.append("  }")
    else:
        lines.append("")
        lines.append("  constructor() {}")

    for method in methods:
        lines.append("")
        lines.append(f"  {method}(): void {{")
        lines.append(f"    // TODO: implement {method}")
        lines.append("    throw new Error('Not implemented');")
        lines.append("  }")

    lines.append("}")
    return "\n".join(lines) + "\n"


def _java_class(name: str, fields: List[str], methods: List[str], base_class: str) -> str:
    extends = f" extends {base_class}" if base_class else ""
    lines = [f"public class {name}{extends} {{"]

    for f in fields:
        lines.append(f"    private Object {f};")

    if fields:
        lines.append("")
        ctor_params = ", ".join(f"Object {f}" for f in fields)
        lines.append(f"    public {name}({ctor_params}) {{")
        for f in fields:
            lines.append(f"        this.{f} = {f};")
        lines.append("    }")
        lines.append("")
        # Getters/setters
        for f in fields:
            cap = f.capitalize()
            lines.append(f"    public Object get{cap}() {{ return {f}; }}")
            lines.append(f"    public void set{cap}(Object {f}) {{ this.{f} = {f}; }}")

    for method in methods:
        lines.append("")
        lines.append(f"    public void {method}() {{")
        lines.append(f"        // TODO: implement {method}")
        lines.append("        throw new UnsupportedOperationException();")
        lines.append("    }")

    lines.append("}")
    return "\n".join(lines) + "\n"
