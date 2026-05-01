"""dependency_check - inspect common dependency manifests."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


def dependency_check(root: str = ".") -> Dict[str, Any]:
    """Read dependency files and return normalized package names/versions."""
    base = Path(root).resolve()
    if not base.exists():
        return {"ok": False, "error": f"Path not found: {root}"}

    result: Dict[str, Any] = {
        "ok": True,
        "root": str(base),
        "python": {"requirements": [], "pyproject": []},
        "node": {"dependencies": {}, "devDependencies": {}},
        "found_files": [],
    }

    req_file = base / "requirements.txt"
    if req_file.exists():
        result["found_files"].append("requirements.txt")
        result["python"]["requirements"] = _parse_requirements(req_file)

    pyproject = base / "pyproject.toml"
    if pyproject.exists():
        result["found_files"].append("pyproject.toml")
        result["python"]["pyproject"] = _parse_pyproject_deps(pyproject)

    package_json = base / "package.json"
    if package_json.exists():
        result["found_files"].append("package.json")
        node = _parse_package_json(package_json)
        result["node"]["dependencies"] = node.get("dependencies", {})
        result["node"]["devDependencies"] = node.get("devDependencies", {})

    return result


def _parse_requirements(path: Path) -> List[str]:
    out: List[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = _REQ_RE.match(line)
        if m:
            out.append(m.group(1))
    return sorted(set(out))


def _parse_pyproject_deps(path: Path) -> List[str]:
    deps: List[str] = []
    in_dep_array = False

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("dependencies") and "[" in line:
            in_dep_array = True
            continue
        if in_dep_array and line.startswith("]"):
            in_dep_array = False
            continue
        if in_dep_array and line.startswith('"'):
            token = line.strip(",").strip().strip('"')
            pkg = re.split(r"[<>=!~ ]", token, maxsplit=1)[0]
            if pkg:
                deps.append(pkg)

    return sorted(set(deps))


def _parse_package_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid package.json: {exc}"}

    return {
        "dependencies": data.get("dependencies", {}),
        "devDependencies": data.get("devDependencies", {}),
    }
