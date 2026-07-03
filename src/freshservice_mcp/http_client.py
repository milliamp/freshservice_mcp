"""Freshservice MCP — Shared HTTP client utilities."""
import base64
import mimetypes
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import FRESHSERVICE_DOMAIN, FRESHSERVICE_APIKEY


def _auth_header() -> str:
    """Return the Basic-auth header value."""
    return f"Basic {base64.b64encode(f'{FRESHSERVICE_APIKEY}:X'.encode()).decode()}"


def get_auth_headers() -> Dict[str, str]:
    """Return Basic-auth + JSON content-type headers (for POST/PUT)."""
    return {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
    }


def get_auth_headers_readonly() -> Dict[str, str]:
    """Return Basic-auth headers only (for GET/DELETE).

    Some Freshservice endpoints (e.g. status/pages) reject GET requests
    that include Content-Type: application/json.
    """
    return {"Authorization": _auth_header()}


def get_auth_headers_multipart() -> Dict[str, str]:
    """Auth headers WITHOUT Content-Type so httpx sets the multipart boundary."""
    return {"Authorization": _auth_header()}


def build_attachment_parts(
    paths: List[str],
) -> List[Tuple[str, Tuple[str, bytes, str]]]:
    """Build httpx multipart parts for Freshservice ``attachments[]`` uploads.

    Returns a list of ``("attachments[]", (filename, bytes, content_type))``
    tuples. Raises FileNotFoundError if any path is missing.

    Freshservice limits: up to 15 files and 40 MB total per request.
    """
    parts: List[Tuple[str, Tuple[str, bytes, str]]] = []
    for path in paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Attachment not found: {path}")
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            parts.append(("attachments[]", (os.path.basename(path), fh.read(), content_type)))
    return parts


async def api_post_multipart(
    path: str,
    data: Dict[str, Any],
    files: List[Tuple[str, Tuple[str, bytes, str]]],
) -> httpx.Response:
    """POST to Freshservice as multipart/form-data (for attachment uploads).

    ``data`` MUST be a dict; on httpx 0.28+ passing a list-of-tuples data
    together with ``files`` raises "Attempted to send an sync request with
    an AsyncClient instance." Dict form works, and list values are still
    repeated for the same key (so ``{"cc_emails[]": ["a", "b"]}`` becomes
    ``cc_emails[]=a & cc_emails[]=b`` in the multipart body).
    """
    async with httpx.AsyncClient() as client:
        return await client.post(
            api_url(path),
            headers=get_auth_headers_multipart(),
            data=data,
            files=files,
        )


def parse_link_header(link_header: str) -> Dict[str, Optional[int]]:
    """Parse the HTTP Link header to extract pagination page numbers."""
    pagination: Dict[str, Optional[int]] = {"next": None, "prev": None}
    if not link_header:
        return pagination
    for link in link_header.split(","):
        match = re.search(r'<(.+?)>;\s*rel="(.+?)"', link)
        if match:
            url, rel = match.groups()
            page_match = re.search(r"page=(\d+)", url)
            if page_match:
                pagination[rel] = int(page_match.group(1))
    return pagination


def api_url(path: str) -> str:
    """Build a full Freshservice API v2 URL."""
    return f"https://{FRESHSERVICE_DOMAIN}/api/v2/{path.lstrip('/')}"


async def api_get(path: str, params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """Perform an authenticated GET request.

    *headers* overrides the default auth-only headers.  Pass
    ``get_auth_headers()`` for endpoints that require Content-Type
    (e.g. ``/api/v2/pm/`` NewGen endpoints).
    """
    async with httpx.AsyncClient() as client:
        return await client.get(
            api_url(path),
            headers=headers or get_auth_headers_readonly(),
            params=params,
        )


async def api_post(path: str, json: Optional[Any] = None) -> httpx.Response:
    """Perform an authenticated POST request."""
    async with httpx.AsyncClient() as client:
        return await client.post(api_url(path), headers=get_auth_headers(), json=json)


async def api_put(path: str, json: Optional[Dict[str, Any]] = None) -> httpx.Response:
    """Perform an authenticated PUT request."""
    async with httpx.AsyncClient() as client:
        return await client.put(api_url(path), headers=get_auth_headers(), json=json)


async def api_delete(path: str,
                     headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """Perform an authenticated DELETE request."""
    async with httpx.AsyncClient() as client:
        return await client.delete(
            api_url(path),
            headers=headers or get_auth_headers_readonly(),
        )


def handle_error(e: Exception, action: str = "request") -> Dict[str, Any]:
    """Standardised error response builder."""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            details = e.response.json()
        except Exception:
            details = e.response.text
        return {"success": False, "error": f"Failed to {action}: {e}", "details": details}
    return {"success": False, "error": f"Unexpected error during {action}: {e}"}


async def _fetch_json(path: str) -> Any:
    """Fetch ``path`` and return decoded JSON; raises on HTTP error."""
    resp = await api_get(path)
    resp.raise_for_status()
    return resp.json()


async def gather_enrichments(jobs: Dict[str, str]) -> Dict[str, Any]:
    """Run parallel sub-fetches; merge into a dict.

    ``jobs`` is a mapping of result-key → API path. Successful fetches land
    at ``result[key]``; failures land at ``result["_" + key + "_warning"]``
    so a partial enrichment failure never kills the parent response.
    """
    import asyncio
    if not jobs:
        return {}
    keys = list(jobs.keys())
    results = await asyncio.gather(
        *[_fetch_json(jobs[k]) for k in keys],
        return_exceptions=True,
    )
    enriched: Dict[str, Any] = {}
    for key, res in zip(keys, results):
        if isinstance(res, Exception):
            enriched[f"_{key}_warning"] = f"Failed to fetch {jobs[key]}: {res}"
        else:
            # Unwrap common Freshservice envelope: {key: [...]} → just the list
            if isinstance(res, dict) and len(res) == 1 and key in res:
                enriched[key] = res[key]
            else:
                enriched[key] = res
    return enriched
