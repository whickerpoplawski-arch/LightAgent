"""First-class web_search / web_fetch tools for LightAgent.

- web_search: ddgs by default (zero cost). Prefer Tavily or Brave only if their API keys
  are set in the environment (still optional / free-tier friendly).
- web_fetch: httpx GET + readability extraction; truncate; SSRF guards.

These are tools (tool_info), not Skills. No OpenRouter usage.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

# ---- tunables -------------------------------------------------------------
SEARCH_MAX_RESULTS = int(os.environ.get("WEB_SEARCH_MAX_RESULTS", "5"))
FETCH_MAX_CHARS = int(os.environ.get("WEB_FETCH_MAX_CHARS", "12000"))
FETCH_TIMEOUT = float(os.environ.get("WEB_FETCH_TIMEOUT", "20"))
USER_AGENT = os.environ.get(
    "WEB_USER_AGENT",
    "LightAgent-web_tools/1.0 (+https://github.com/wanxingai/LightAgent)",
)

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
}


class _StripHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "\n".join(self._chunks)).strip()


# Some sandboxes rewrite public DNS to 198.18.0.0/15 (benchmark / transparent proxy).
# Treat that range as reachable egress, not SSRF — still block RFC1918/loopback/link-local.
_SANDBOX_DNS_REWRITE = ipaddress.ip_network("198.18.0.0/15")


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.version == 4 and ip in _SANDBOX_DNS_REWRITE:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolve_and_check_host(hostname: str) -> list[str]:
    host = (hostname or "").strip(".").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        raise ValueError(f"SSRF blocked host: {hostname!r}")
    try:
        # Literal IP in hostname
        ip = ipaddress.ip_address(host)
        if _is_private_ip(ip):
            raise ValueError(f"SSRF blocked private IP: {host}")
        return [host]
    except ValueError as e:
        if "SSRF" in str(e):
            raise
        # not an IP literal — resolve
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    addrs: list[str] = []
    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr)
        if _is_private_ip(ip):
            raise ValueError(f"SSRF blocked: {host} resolves to private {addr}")
        addrs.append(addr)
    if not addrs:
        raise ValueError(f"could not resolve host: {host}")
    return addrs


def _validate_fetch_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("url is empty")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"only http/https allowed, got scheme={parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("url missing hostname")
    if parsed.username or parsed.password:
        raise ValueError("SSRF blocked: URL userinfo not allowed")
    _resolve_and_check_host(parsed.hostname)
    return raw


def _extract_text(html: str, url: str) -> str:
    # Prefer trafilatura → html2text → readability → naive strip
    try:
        import trafilatura

        out = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
        if out and out.strip():
            return out.strip()
    except Exception:
        pass
    try:
        import html2text

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        out = h.handle(html)
        if out and out.strip():
            return out.strip()
    except Exception:
        pass
    try:
        from readability import Document  # readability-lxml

        doc = Document(html)
        summary_html = doc.summary() or ""
        title = doc.title() or ""
        parser = _StripHTML()
        parser.feed(summary_html)
        body = parser.text()
        if body:
            return f"# {title}\n\n{body}" if title else body
    except Exception:
        pass
    parser = _StripHTML()
    parser.feed(html)
    return parser.text()


def _truncate(text: str, limit: int = FETCH_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n\n…[truncated]"


def _search_tavily(query: str, max_results: int) -> list[dict[str, Any]]:
    import httpx

    key = os.environ["TAVILY_API_KEY"]
    payload = {
        "api_key": key,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "search_depth": "basic",
    }
    with httpx.Client(timeout=FETCH_TIMEOUT) as client:
        r = client.post("https://api.tavily.com/search", json=payload)
        r.raise_for_status()
        data = r.json()
    rows = []
    for item in data.get("results") or []:
        rows.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("content") or item.get("snippet") or "",
                "provider": "tavily",
            }
        )
    return rows


def _search_brave(query: str, max_results: int) -> list[dict[str, Any]]:
    import httpx

    key = os.environ["BRAVE_API_KEY"]
    headers = {"X-Subscription-Token": key, "Accept": "application/json"}
    params = {"q": query, "count": max_results}
    with httpx.Client(timeout=FETCH_TIMEOUT) as client:
        r = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
        )
        r.raise_for_status()
        data = r.json()
    rows = []
    for item in (data.get("web") or {}).get("results") or []:
        rows.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("description") or "",
                "provider": "brave",
            }
        )
    return rows


def _search_ddgs(query: str, max_results: int) -> list[dict[str, Any]]:
    try:
        from ddgs import DDGS
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "ddgs is required for free web_search. "
            "Install with: poetry run pip install ddgs"
        ) from e
    rows: list[dict[str, Any]] = []
    ddgs = DDGS()
    for item in ddgs.text(query, max_results=max_results) or []:
        rows.append(
            {
                "title": item.get("title") or "",
                "url": item.get("href") or item.get("link") or "",
                "snippet": item.get("body") or item.get("snippet") or "",
                "provider": "ddgs",
            }
        )
    return rows


def web_search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> str:
    """Search the public web. Default provider is free ddgs; Tavily/Brave if keys set."""
    q = (query or "").strip()
    if not q:
        return json.dumps({"error": "empty query", "results": []}, ensure_ascii=False)
    n = max(1, min(int(max_results or SEARCH_MAX_RESULTS), 10))
    provider = "ddgs"
    try:
        if os.environ.get("TAVILY_API_KEY"):
            provider = "tavily"
            results = _search_tavily(q, n)
        elif os.environ.get("BRAVE_API_KEY"):
            provider = "brave"
            results = _search_brave(q, n)
        else:
            results = _search_ddgs(q, n)
    except Exception as e:
        return json.dumps(
            {"error": str(e), "provider": provider, "query": q, "results": []},
            ensure_ascii=False,
        )
    return json.dumps(
        {"query": q, "provider": provider, "count": len(results), "results": results},
        ensure_ascii=False,
    )


web_search.tool_info = {
    "tool_name": "web_search",
    "tool_title": "网页搜索",
    "tool_description": (
        "Search the public web and return titles, URLs, and snippets. "
        "Uses free DuckDuckGo (ddgs) by default; if TAVILY_API_KEY or BRAVE_API_KEY "
        "is set, that provider is preferred. No OpenRouter cost."
    ),
    "tool_params": [
        {
            "name": "query",
            "description": "Search query string",
            "type": "string",
            "required": True,
        },
        {
            "name": "max_results",
            "description": "Max results (1-10, default 5)",
            "type": "integer",
            "required": False,
        },
    ],
}


def web_fetch(url: str, max_chars: int = FETCH_MAX_CHARS) -> str:
    """Fetch a public http(s) URL and return extracted readable text (truncated)."""
    import httpx

    try:
        safe_url = _validate_fetch_url(url)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)

    limit = max(500, min(int(max_chars or FETCH_MAX_CHARS), 100_000))
    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
            max_redirects=5,
        ) as client:
            # Re-validate after redirects: check final URL host
            resp = client.get(safe_url)
            final = str(resp.url)
            try:
                _validate_fetch_url(final)
            except Exception as e:
                return json.dumps(
                    {"error": f"SSRF blocked after redirect: {e}", "url": url, "final_url": final},
                    ensure_ascii=False,
                )
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            raw = resp.text
    except Exception as e:
        return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)

    if "html" in ctype or raw.lstrip().startswith("<") or "<html" in raw[:200].lower():
        text = _extract_text(raw, final)
    else:
        text = raw

    text = _truncate(text, limit)
    return json.dumps(
        {
            "url": url,
            "final_url": final,
            "status_code": resp.status_code,
            "content_type": ctype,
            "chars": len(text),
            "text": text,
        },
        ensure_ascii=False,
    )


web_fetch.tool_info = {
    "tool_name": "web_fetch",
    "tool_title": "抓取网页",
    "tool_description": (
        "Fetch a public http(s) URL and return readable text (HTML stripped / "
        "readability extracted), truncated. Blocks localhost and private IPs (SSRF). "
        "Prefer this for static pages; use the browser-use skill for JS-heavy sites."
    ),
    "tool_params": [
        {
            "name": "url",
            "description": "Absolute http or https URL to fetch",
            "type": "string",
            "required": True,
        },
        {
            "name": "max_chars",
            "description": "Max characters of extracted text (default 12000)",
            "type": "integer",
            "required": False,
        },
    ],
}
