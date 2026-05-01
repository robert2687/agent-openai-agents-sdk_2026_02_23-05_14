"""create_api_endpoint — generate REST endpoint stub code for common frameworks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


_FRAMEWORKS = {"fastapi", "flask", "express", "django"}
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def create_api_endpoint(
    route: str,
    *,
    method: str = "GET",
    handler_name: str = "",
    framework: str = "fastapi",
    output_path: str = "",
    include_schema: bool = True,
) -> Dict[str, Any]:
    """Generate a REST endpoint stub for a given framework.

    Args:
        route: URL route path, e.g. "/users/{user_id}".
        method: HTTP method — GET, POST, PUT, PATCH, or DELETE.
        handler_name: Function/handler name (auto-derived from route if empty).
        framework: "fastapi", "flask", "express", or "django".
        output_path: If given, write the generated code to this file.
        include_schema: Include a request/response schema stub (Pydantic / TypeScript interface).

    Returns:
        dict with ``content`` (generated code string) and optionally ``written``.
    """
    fw = framework.strip().lower()
    meth = method.strip().upper()

    if fw not in _FRAMEWORKS:
        return {"ok": False, "error": f"Unknown framework '{framework}'. Use: {sorted(_FRAMEWORKS)}"}
    if meth not in _METHODS:
        return {"ok": False, "error": f"Unknown method '{method}'. Use: {sorted(_METHODS)}"}

    if not handler_name:
        handler_name = _derive_handler_name(route, meth)

    generators = {
        "fastapi": _fastapi_endpoint,
        "flask": _flask_endpoint,
        "express": _express_endpoint,
        "django": _django_endpoint,
    }
    content = generators[fw](route, meth, handler_name, include_schema)
    result: Dict[str, Any] = {
        "ok": True,
        "framework": fw,
        "method": meth,
        "route": route,
        "handler_name": handler_name,
        "content": content,
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        result["written"] = str(out)

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _derive_handler_name(route: str, method: str) -> str:
    parts = [p.strip("{}") for p in route.strip("/").split("/") if p]
    base = "_".join(parts) if parts else "root"
    return f"{method.lower()}_{base}"


# ── Framework generators ──────────────────────────────────────────────────────

def _fastapi_endpoint(route: str, method: str, name: str, schema: bool) -> str:
    lines = [
        "from fastapi import APIRouter, HTTPException",
    ]
    if schema:
        lines += [
            "from pydantic import BaseModel",
            "",
            "",
            "class RequestBody(BaseModel):",
            "    # TODO: define request fields",
            "    pass",
            "",
            "",
            "class ResponseBody(BaseModel):",
            "    # TODO: define response fields",
            "    message: str",
        ]
    lines += [
        "",
        "",
        "router = APIRouter()",
        "",
        "",
        f'@router.{method.lower()}("{route}")',
    ]
    if method in {"POST", "PUT", "PATCH"} and schema:
        lines.append(f"async def {name}(body: RequestBody) -> ResponseBody:")
    else:
        lines.append(f"async def {name}() -> dict:")
    lines += [
        f'    """Handle {method} {route}."""',
        "    # TODO: implement handler",
        '    return {"message": "ok"}',
    ]
    return "\n".join(lines) + "\n"


def _flask_endpoint(route: str, method: str, name: str, schema: bool) -> str:
    lines = [
        "from flask import Blueprint, request, jsonify",
        "",
        "",
        "bp = Blueprint('api', __name__)",
        "",
        "",
        f'@bp.route("{route}", methods=["{method}"])',
        f"def {name}():",
        f'    """Handle {method} {route}."""',
    ]
    if method in {"POST", "PUT", "PATCH"}:
        lines += [
            "    data = request.get_json()",
            "    # TODO: validate and process data",
        ]
    lines += [
        "    # TODO: implement handler",
        '    return jsonify({"message": "ok"}), 200',
    ]
    return "\n".join(lines) + "\n"


def _express_endpoint(route: str, method: str, name: str, schema: bool) -> str:
    ts_route = route.replace("{", ":").replace("}", "")
    if schema:
        iface_lines = [
            "interface RequestBody {",
            "  // TODO: define request fields",
            "}",
            "",
            "interface ResponseBody {",
            "  message: string;",
            "}",
            "",
        ]
    else:
        iface_lines = []

    lines = [
        "import { Router, Request, Response } from 'express';",
        "",
        "const router = Router();",
        "",
    ] + iface_lines + [
        f"router.{method.lower()}('{ts_route}', async (req: Request, res: Response) => {{",
        f"  // TODO: implement {method} {route}",
        "  res.json({ message: 'ok' });",
        "});",
        "",
        "export default router;",
    ]
    return "\n".join(lines) + "\n"


def _django_endpoint(route: str, method: str, name: str, schema: bool) -> str:
    lines = [
        "from django.http import JsonResponse",
        "from django.views import View",
        "import json",
        "",
        "",
        f"class {name.title().replace('_', '')}View(View):",
        f'    """Handle {method} {route}."""',
        "",
    ]
    m = method.lower()
    lines += [
        f"    def {m}(self, request, *args, **kwargs):",
    ]
    if method in {"POST", "PUT", "PATCH"}:
        lines += [
            "        try:",
            "            data = json.loads(request.body)",
            "        except json.JSONDecodeError:",
            "            return JsonResponse({'error': 'Invalid JSON'}, status=400)",
            "        # TODO: process data",
        ]
    lines += [
        "        # TODO: implement handler",
        "        return JsonResponse({'message': 'ok'})",
    ]
    return "\n".join(lines) + "\n"
