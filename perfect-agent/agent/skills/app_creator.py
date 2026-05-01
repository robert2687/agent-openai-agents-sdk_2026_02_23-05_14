"""app_creator - scaffold small starter apps on disk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def app_creator(
    app_type: str,
    name: str,
    *,
    root: str = ".",
) -> Dict[str, Any]:
    """Create a starter app skeleton.

    Supported types: python_cli, fastapi, node_api, static_web.
    """
    t = app_type.strip().lower()
    base = Path(root).resolve() / name
    created: List[str] = []

    if base.exists():
        return {"ok": False, "error": f"Target already exists: {base}"}

    base.mkdir(parents=True, exist_ok=False)

    try:
        if t == "python_cli":
            created += _scaffold_python_cli(base, name)
        elif t == "fastapi":
            created += _scaffold_fastapi(base, name)
        elif t == "node_api":
            created += _scaffold_node_api(base, name)
        elif t == "static_web":
            created += _scaffold_static_web(base, name)
        else:
            return {"ok": False, "error": "Unsupported app_type. Use: python_cli, fastapi, node_api, static_web"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "created": created}

    return {
        "ok": True,
        "app_type": t,
        "name": name,
        "root": str(base),
        "created": created,
    }


def _write(path: Path, content: str, created: List[str], base: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(str(path.relative_to(base)))


def _scaffold_python_cli(base: Path, name: str) -> List[str]:
    created: List[str] = []
    _write(
        base / "main.py",
        "def main() -> None:\n"
        "    print('Hello from python cli app')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        created,
        base,
    )
    _write(base / "requirements.txt", "", created, base)
    _write(
        base / "README.md",
        f"# {name}\n\nRun:\n\npython main.py\n",
        created,
        base,
    )
    return created


def _scaffold_fastapi(base: Path, name: str) -> List[str]:
    created: List[str] = []
    _write(
        base / "app" / "main.py",
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "@app.get('/health')\n"
        "def health() -> dict:\n"
        "    return {'status': 'ok'}\n",
        created,
        base,
    )
    _write(base / "requirements.txt", "fastapi\nuvicorn\n", created, base)
    _write(
        base / "README.md",
        f"# {name}\n\nRun:\n\nuvicorn app.main:app --reload\n",
        created,
        base,
    )
    return created


def _scaffold_node_api(base: Path, name: str) -> List[str]:
    created: List[str] = []
    package_json = {
        "name": name,
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "scripts": {"start": "node src/index.js"},
        "dependencies": {"express": "^4.19.2"},
    }
    _write(base / "package.json", json.dumps(package_json, indent=2) + "\n", created, base)
    _write(
        base / "src" / "index.js",
        "import express from 'express';\n\n"
        "const app = express();\n"
        "app.get('/health', (_req, res) => res.json({ status: 'ok' }));\n"
        "app.listen(3000, () => console.log('Server on http://localhost:3000'));\n",
        created,
        base,
    )
    _write(base / "README.md", f"# {name}\n\nRun:\n\nnpm install\nnpm start\n", created, base)
    return created


def _scaffold_static_web(base: Path, name: str) -> List[str]:
    created: List[str] = []
    _write(
        base / "index.html",
        "<!doctype html>\n"
        "<html lang='en'>\n"
        "<head>\n"
        "  <meta charset='utf-8'/>\n"
        "  <meta name='viewport' content='width=device-width, initial-scale=1'/>\n"
        f"  <title>{name}</title>\n"
        "  <link rel='stylesheet' href='styles.css'/>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <h1>Hello from generated static app</h1>\n"
        "    <p>Edit index.html to get started.</p>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n",
        created,
        base,
    )
    _write(
        base / "styles.css",
        "body {\n"
        "  font-family: Georgia, 'Times New Roman', serif;\n"
        "  margin: 0;\n"
        "  min-height: 100vh;\n"
        "  display: grid;\n"
        "  place-items: center;\n"
        "  background: linear-gradient(120deg, #f4efe6, #d8e9f2);\n"
        "}\n"
        "main {\n"
        "  background: rgba(255,255,255,0.8);\n"
        "  border: 1px solid #b4c8d3;\n"
        "  border-radius: 14px;\n"
        "  padding: 2rem;\n"
        "}\n",
        created,
        base,
    )
    _write(base / "README.md", f"# {name}\n\nOpen index.html in a browser.\n", created, base)
    return created
