"""HTTP tools for PERFECT-AGENT."""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from agent import config


def _build_response(resp: requests.Response) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "status": resp.status_code,
        "ok": resp.ok,
        "url": resp.url,
        "text": resp.text,
    }
    try:
        data["json"] = resp.json()
    except ValueError:
        data["json"] = None
    return data


def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: int = config.HTTP_TIMEOUT,
) -> Dict[str, Any]:
    """Perform an HTTP GET request and return status, headers, and body."""
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        return _build_response(resp)
    except requests.RequestException as exc:
        return {"status": None, "ok": False, "url": url, "text": "", "json": None, "error": str(exc)}


def http_post(
    url: str,
    json_body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = config.HTTP_TIMEOUT,
) -> Dict[str, Any]:
    """Perform an HTTP POST request with a JSON body."""
    try:
        resp = requests.post(url, json=json_body, headers=headers, timeout=timeout)
        return _build_response(resp)
    except requests.RequestException as exc:
        return {"status": None, "ok": False, "url": url, "text": "", "json": None, "error": str(exc)}
