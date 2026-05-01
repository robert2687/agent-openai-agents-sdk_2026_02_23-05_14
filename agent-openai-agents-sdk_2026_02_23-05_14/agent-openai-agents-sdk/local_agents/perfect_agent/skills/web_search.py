"""web_search — lightweight web search via DuckDuckGo HTML (no API key required).

Scrapes DuckDuckGo's lite HTML endpoint, which is reliably available and
returns clean text snippets — no JS required, no rate-limit API key needed.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List

try:
    import requests as _requests  # preferred
    _USE_REQUESTS = True
except ImportError:
    import urllib.request as _urllib_req  # stdlib fallback
    _USE_REQUESTS = False


_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; perfect-agent/1.0; +https://github.com/robert2687)",
    "Accept-Language": "en-US,en;q=0.9",
}


def web_search(
    query: str,
    *,
    max_results: int = 8,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Search the web using DuckDuckGo and return structured results.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 8).
        timeout: HTTP timeout in seconds.

    Returns:
        dict with keys:
          - ``results``: list of dicts with ``title``, ``url``, ``snippet``
          - ``total``: number of results returned
          - ``query``: the query as sent
    """
    try:
        html = _fetch(query, timeout)
    except Exception as exc:  # noqa: BLE001
        return {"results": [], "total": 0, "query": query, "error": str(exc)}

    results = _parse(html, max_results)
    return {"results": results, "total": len(results), "query": query}


def _fetch(query: str, timeout: int) -> str:
    data = urllib.parse.urlencode({"q": query, "kl": "us-en"})
    if _USE_REQUESTS:
        resp = _requests.post(_DDG_URL, data=data, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    # stdlib fallback
    req = _urllib_req.Request(  # type: ignore[attr-defined]
        _DDG_URL,
        data=data.encode(),
        headers=_HEADERS,
    )
    with _urllib_req.urlopen(req, timeout=timeout) as r:  # type: ignore[attr-defined]
        return r.read().decode("utf-8", errors="replace")


def _parse(html: str, max_results: int) -> List[Dict[str, str]]:
    """Extract title/url/snippet triples from DuckDuckGo HTML lite."""
    results: List[Dict[str, str]] = []

    # DuckDuckGo HTML lite structure (simplified regex extraction)
    # Each result block contains a link and a snippet
    blocks = re.split(r'class="result__body"', html)
    for block in blocks[1 : max_results + 1]:  # first split is preamble
        # Title + URL
        title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)<', block)
        # Snippet
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.+?)</a>', block, re.DOTALL)

        if not title_match:
            continue

        url = _clean_ddg_url(title_match.group(1))
        title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip() if snippet_match else ""
        snippet = re.sub(r"\s+", " ", snippet)

        results.append({"title": title, "url": url, "snippet": snippet})

    return results


def _clean_ddg_url(raw: str) -> str:
    """Strip DuckDuckGo redirect wrappers to get the bare target URL."""
    # DDG HTML links look like //duckduckgo.com/l/?uddg=<encoded_url>
    if "uddg=" in raw:
        m = re.search(r"uddg=([^&]+)", raw)
        if m:
            return urllib.parse.unquote(m.group(1))
    if raw.startswith("//"):
        return "https:" + raw
    return raw
