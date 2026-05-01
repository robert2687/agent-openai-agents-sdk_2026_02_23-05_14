"""code_generator - produce starter code files for common coding tasks."""
from __future__ import annotations

from typing import Any, Dict


def code_generator(
    kind: str,
    *,
    language: str = "python",
    name: str = "example",
    include_tests: bool = True,
) -> Dict[str, Any]:
    """Generate starter code snippets for common tasks.

    Args:
        kind: One of "function", "class", "script", "api_handler".
        language: "python" or "typescript".
        name: Symbol or file stem name.
        include_tests: Include a matching unit-test snippet when supported.

    Returns:
        dict with generated file content in a files map.
    """
    k = kind.strip().lower()
    lang = language.strip().lower()

    if lang not in {"python", "typescript"}:
        return {"ok": False, "error": f"Unsupported language: {language}"}

    if k == "function":
        return _gen_function(lang, name, include_tests)
    if k == "class":
        return _gen_class(lang, name, include_tests)
    if k == "script":
        return _gen_script(lang, name)
    if k == "api_handler":
        return _gen_api_handler(lang, name)

    return {
        "ok": False,
        "error": "Unknown kind. Use: function, class, script, api_handler",
    }


def _gen_function(lang: str, name: str, include_tests: bool) -> Dict[str, Any]:
    if lang == "python":
        fn = (
            f"def {name}(value: int) -> int:\n"
            f"    \"\"\"Return a transformed value.\"\"\"\n"
            f"    return value * 2\n"
        )
        files = {f"{name}.py": fn}
        if include_tests:
            files[f"test_{name}.py"] = (
                f"from {name} import {name}\n\n"
                f"def test_{name}() -> None:\n"
                f"    assert {name}(3) == 6\n"
            )
        return {"ok": True, "files": files, "language": lang, "kind": "function"}

    fn_ts = (
        f"export function {name}(value: number): number {{\n"
        f"  return value * 2;\n"
        f"}}\n"
    )
    files = {f"{name}.ts": fn_ts}
    if include_tests:
        files[f"{name}.test.ts"] = (
            f"import {{ {name} }} from './{name}';\n\n"
            f"test('{name}', () => {{\n"
            f"  expect({name}(3)).toBe(6);\n"
            f"}});\n"
        )
    return {"ok": True, "files": files, "language": lang, "kind": "function"}


def _gen_class(lang: str, name: str, include_tests: bool) -> Dict[str, Any]:
    class_name = "".join(part.capitalize() for part in name.split("_")) or "Example"

    if lang == "python":
        src = (
            f"class {class_name}:\n"
            f"    def __init__(self, label: str) -> None:\n"
            f"        self.label = label\n\n"
            f"    def describe(self) -> str:\n"
            f"        return f'{class_name}: {{self.label}}'\n"
        )
        files = {f"{name}.py": src}
        if include_tests:
            files[f"test_{name}.py"] = (
                f"from {name} import {class_name}\n\n"
                f"def test_describe() -> None:\n"
                f"    obj = {class_name}('demo')\n"
                f"    assert obj.describe() == '{class_name}: demo'\n"
            )
        return {"ok": True, "files": files, "language": lang, "kind": "class"}

    src_ts = (
        f"export class {class_name} {{\n"
        f"  constructor(private label: string) {{}}\n\n"
        f"  describe(): string {{\n"
        f"    return '{class_name}: ' + this.label;\n"
        f"  }}\n"
        f"}}\n"
    )
    files = {f"{name}.ts": src_ts}
    if include_tests:
        files[f"{name}.test.ts"] = (
            f"import {{ {class_name} }} from './{name}';\n\n"
            f"test('describe', () => {{\n"
            f"  expect(new {class_name}('demo').describe()).toBe('{class_name}: demo');\n"
            f"}});\n"
        )
    return {"ok": True, "files": files, "language": lang, "kind": "class"}


def _gen_script(lang: str, name: str) -> Dict[str, Any]:
    if lang == "python":
        src = (
            "def main() -> None:\n"
            "    print('Hello from generated script')\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return {"ok": True, "files": {f"{name}.py": src}, "language": lang, "kind": "script"}

    src_ts = (
        "function main(): void {\n"
        "  console.log('Hello from generated script');\n"
        "}\n\n"
        "main();\n"
    )
    return {"ok": True, "files": {f"{name}.ts": src_ts}, "language": lang, "kind": "script"}


def _gen_api_handler(lang: str, name: str) -> Dict[str, Any]:
    if lang == "python":
        src = (
            "from fastapi import APIRouter\n\n"
            "router = APIRouter()\n\n"
            f"@router.get('/{name}')\n"
            f"def get_{name}() -> dict:\n"
            "    return {'ok': True}\n"
        )
        return {"ok": True, "files": {f"{name}_handler.py": src}, "language": lang, "kind": "api_handler"}

    src_ts = (
        "import { Request, Response } from 'express';\n\n"
        f"export function get{name.title().replace('_', '')}(req: Request, res: Response): void {{\n"
        "  res.json({ ok: true });\n"
        "}\n"
    )
    return {"ok": True, "files": {f"{name}Handler.ts": src_ts}, "language": lang, "kind": "api_handler"}
