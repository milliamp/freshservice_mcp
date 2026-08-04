"""Freshservice MCP — Tickets tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  • read_ticket / manage_ticket
      — ticket CRUD plus sub-entities: conversations, tasks, time entries,
        and approvals. One action dispatch table per tool.
  • read_service_catalog / manage_service_catalog
      — service-catalog browsing + service-request placement (sibling of
        tickets; not folded into manage_ticket).
"""
import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from mcp.server.fastmcp import Image

from ..cache import REQUESTED_ITEMS_KEY, read_cache, write_cache
from ..config import (
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from ..discovery import fetch_service_items, resolve_item_selectors
from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_post_multipart,
    api_put,
    build_attachment_parts,
    download_bytes,
    fetch_json_bounded,
    gather_enrichments,
    handle_error,
    parse_link_header,
)
from ._split import coerce_payload, normalize_action, reject_unless_in


# ── image content helpers ──────────────────────────────────────────────────
# Freshservice caps single attachments at 40 MB; base64-encoding an image
# roughly triples its wire size, so downloading big files bogs down the LLM
# even more than the flag was meant to avoid. These caps keep the response
# in a range Claude can actually consume.
_MAX_IMAGE_BYTES = 5 * 1024 * 1024        # per-image
_MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024  # across the whole response
_MAX_IMAGES = 20

# Match <img src="..."> (or single-quoted) in HTML bodies. Inline-pasted
# screenshots in Freshservice descriptions/conversations land here.
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

# Format hint FastMCP.Image accepts (must be the subtype only, not a MIME).
_MIME_TO_FORMAT: Dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/svg+xml": "svg+xml",
}


def _collect_image_refs(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return image references found on a ticket or conversation dict.

    Two sources:
      1. ``attachments[]`` entries whose ``content_type`` starts with ``image/``
      2. ``<img src>`` tags in the ``description`` / ``body`` HTML, skipping
         data: URIs and any URL already covered by an attachment record.

    Each ref has: ``url``, ``mime`` (may be empty for inline srcs), ``name``,
    ``source`` ("attachment" or "inline"), ``origin`` ("ticket"/"conversation:<id>").
    """
    refs: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for att in obj.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        mime = (att.get("content_type") or "").lower()
        url = att.get("attachment_url")
        if not url or not mime.startswith("image/"):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        refs.append({
            "url": url,
            "mime": mime,
            "name": att.get("name") or "attachment",
            "source": "attachment",
            "attachment_id": att.get("id"),
        })

    for html_field in ("description", "body"):
        html = obj.get(html_field)
        if not isinstance(html, str) or not html:
            continue
        for src in _IMG_SRC_RE.findall(html):
            if src.startswith("data:") or src in seen_urls:
                continue
            seen_urls.add(src)
            refs.append({
                "url": src,
                "mime": "",
                "name": src.rsplit("/", 1)[-1][:80] or "inline",
                "source": "inline",
            })

    return refs


async def _gather_images(refs: List[Dict[str, Any]]) -> Tuple[List[Image], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Download refs sequentially, honoring per-image and total byte caps.

    Sequential (not gather) so we can enforce the running total; the extra
    latency is fine since this is off by default and a single ticket rarely
    has more than a handful of screenshots.

    Returns ``(images, manifest_entries, skipped_entries)``.
    """
    images: List[Image] = []
    manifest: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    total = 0

    for ref in refs[:_MAX_IMAGES]:
        remaining = _MAX_TOTAL_IMAGE_BYTES - total
        if remaining <= 0:
            skipped.append({**ref, "reason": "total size cap reached"})
            continue
        try:
            data, content_type = await download_bytes(ref["url"], max_bytes=min(_MAX_IMAGE_BYTES, remaining))
        except Exception as e:  # noqa: BLE001
            skipped.append({**ref, "reason": f"download failed: {e}"})
            continue

        mime = (content_type or ref.get("mime") or "").lower()
        if not mime.startswith("image/"):
            skipped.append({**ref, "reason": f"not an image (content-type: {mime or 'unknown'})"})
            continue

        fmt = _MIME_TO_FORMAT.get(mime, "png")
        entry: Dict[str, Any] = {
            "name": ref.get("name"),
            "source": ref.get("source"),
            "url": ref["url"],
            "content_type": mime,
            "size": len(data),
        }
        if ref.get("attachment_id") is not None:
            entry["attachment_id"] = ref["attachment_id"]
        if ref.get("origin"):
            entry["origin"] = ref["origin"]

        images.append(Image(data=data, format=fmt))
        manifest.append(entry)
        total += len(data)

    if len(refs) > _MAX_IMAGES:
        for ref in refs[_MAX_IMAGES:]:
            skipped.append({**ref, "reason": f"image count cap reached ({_MAX_IMAGES})"})

    return images, manifest, skipped


def _validate_pagination(page: int, per_page: int) -> Optional[Dict[str, Any]]:
    if page < 1:
        return {"error": "Page number must be greater than 0"}
    if per_page < 1 or per_page > 100:
        return {"error": "Page size must be between 1 and 100"}
    return None


# ── requested-item scan ────────────────────────────────────────────────────
# Freshservice has no server-side filter for requested catalog items, so
# "which tickets request item 34?" has to be answered by scanning: run a
# server-side prefilter, then GET /tickets/{id}/requested_items per candidate.
#
# Only these ticket types can carry requested items, so the fan-out skips
# everything else. /tickets/filter cannot narrow by type server-side (verified
# live: `type`, `ticket_type` and `type_id` all 400 with "Unexpected/invalid
# field"), but each ticket in the filter response does carry `type`, so the
# gate is free client-side — it removed ~43% of the fan-out on a real tenant.
_REQUESTED_ITEM_TYPES = {"Service Request"}

_FILTER_PAGE_SIZE = 30              # tickets/filter ignores per_page
_SCAN_MAX_DEFAULT = 200
_SCAN_MAX_CEILING = 500
_SCAN_CONCURRENCY_DEFAULT = 5
_SCAN_CONCURRENCY_MAX = 10
_ITEM_CACHE_MAX_ENTRIES = 2000
_ITEMS_PER_TICKET_PAGE = 30         # a full page hints the sub-endpoint paginated

# Trimmed projections. One requested item's custom_fields blob runs to several
# KB; handing 30+ of them back raw would swamp the model's context window.
_ITEM_SUMMARY_FIELDS = ("id", "service_item_id", "service_item_name",
                        "quantity", "stage", "is_parent")
_TICKET_SUMMARY_FIELDS = ("id", "subject", "type", "status", "status_name",
                          "priority", "requester_id", "requested_for_id",
                          "group_id", "department_id", "created_at",
                          "updated_at", "due_by")


def _summarise_errors(errors: Dict[Any, str], sample: int = 3) -> List[Dict[str, Any]]:
    """Group per-ticket fetch failures by message so a rate-limit storm reads
    as one line rather than N near-identical paragraphs."""
    groups: Dict[str, List[Any]] = {}
    for tid, msg in errors.items():
        # Collapse the URL out of the message so identical failures group.
        key = re.sub(r"https?://\S+", "<url>", str(msg)).split("\n")[0].strip()
        groups.setdefault(key, []).append(tid)
    out = []
    for msg, tids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        entry: Dict[str, Any] = {"error": msg, "ticket_count": len(tids),
                                 "ticket_ids": tids[:sample]}
        if len(tids) > sample:
            entry["ticket_ids_truncated"] = True
        out.append(entry)
    return out


def _trim(src: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    """Project *src* down to *fields* (missing keys are simply absent)."""
    return {k: src[k] for k in fields if k in src}


def _trim_item(item: Dict[str, Any], include_custom_fields: bool = False) -> Dict[str, Any]:
    out = _trim(item, _ITEM_SUMMARY_FIELDS)
    if include_custom_fields and "custom_fields" in item:
        out["custom_fields"] = item["custom_fields"]
    return out


def _coerce_selectors(raw: Any) -> Optional[List[Union[int, str]]]:
    """Normalise an ``items``-style argument into a list of ids / name terms.

    Tolerates the shapes MCP clients actually send: a real list, a JSON string
    (``"[34, 39]"``), a comma-separated string (``"34,39"`` or
    ``"Desk Move, Headphones"``), or a bare int/str. Returns None when nothing
    was supplied, so callers can distinguish "absent" from "empty".
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return [int(raw)]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [x for x in parsed if x is not None and x != ""]
            except (json.JSONDecodeError, TypeError):
                pass
        # Comma-separated fallback. Safe only while no catalog item name
        # contains a comma; payload.item_names is the escape hatch if one does.
        return [p.strip() for p in s.split(",") if p.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [x for x in raw if x is not None and x != ""]
    return [raw]


def _selector_matches(sel: Dict[str, Any], item: Dict[str, Any]) -> bool:
    """True if *item* satisfies one resolved selector (display_id OR name term)."""
    sid = item.get("service_item_id")
    if sid is not None:
        try:
            if int(sid) in sel["display_ids"]:
                return True
        except (TypeError, ValueError):
            pass
    name = (item.get("service_item_name") or "").lower()
    return any(term in name for term in sel["terms"])


def _rollup_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group items by service_item_id, summing quantity across line items.

    One Service Request can carry the same catalog item on several lines, so
    the per-item total is what "who wants 2+ monitors?" actually means.
    """
    grouped: Dict[Any, Dict[str, Any]] = {}
    for item in items:
        sid = item.get("service_item_id")
        g = grouped.setdefault(sid, {
            "service_item_id": sid,
            "service_item_name": item.get("service_item_name"),
            "quantity": 0,
            "line_items": 0,
            "stages": [],
        })
        try:
            g["quantity"] += int(item.get("quantity") or 1)
        except (TypeError, ValueError):
            g["quantity"] += 1
        g["line_items"] += 1
        stage = item.get("stage")
        if stage is not None and stage not in g["stages"]:
            g["stages"].append(stage)
    return list(grouped.values())


async def _filter_tickets_all_pages(
    query: str,
    workspace_id: Optional[int],
    max_tickets: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Walk ``tickets/filter`` pages, stopping once *max_tickets* is reached.

    Returns ``(tickets, meta)``. ``meta`` carries the endpoint's own ``total``,
    pages fetched, truncated/truncation_reason, and — if the walk died part-way
    — ``error``, because a partial answer with an honest error beats none.
    """
    encoded = urllib.parse.quote(f'"{query}"')
    suffix = f"&workspace_id={workspace_id}" if workspace_id is not None else ""
    tickets: List[Dict[str, Any]] = []
    seen: Set[Any] = set()
    meta: Dict[str, Any] = {
        "total": None, "pages": 0, "truncated": False, "truncation_reason": None,
    }
    page = 1
    while True:
        try:
            resp = await api_get(f"tickets/filter?query={encoded}&page={page}{suffix}")
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:
            meta["error"] = f"Failed to filter tickets on page {page}: {e}"
            meta["truncated"] = True
            meta["truncation_reason"] = "error"
            break

        meta["pages"] = page
        if meta["total"] is None:
            meta["total"] = body.get("total")

        batch = body.get("tickets") or []
        for t in batch:
            tid = t.get("id")
            if tid in seen:  # records shift between page fetches on a busy tenant
                continue
            seen.add(tid)
            tickets.append(t)

        if len(batch) < _FILTER_PAGE_SIZE:
            break  # short page == last page
        if isinstance(meta["total"], int) and len(tickets) >= meta["total"]:
            break  # got them all; don't spend a request proving the next page is empty
        if len(tickets) >= max_tickets:
            meta["truncated"] = True
            meta["truncation_reason"] = "max_scan"
            break
        page += 1

    if len(tickets) > max_tickets:
        tickets = tickets[:max_tickets]
        meta["truncated"] = True
        meta["truncation_reason"] = meta["truncation_reason"] or "max_scan"

    # The endpoint's own count is the most reliable truncation signal.
    total = meta.get("total")
    if isinstance(total, int) and len(tickets) < total:
        meta["truncated"] = True
        meta["truncation_reason"] = meta["truncation_reason"] or "max_scan"

    return tickets, meta


async def _requested_items_for(
    tickets: List[Dict[str, Any]],
    concurrency: int,
    include_custom_fields: bool,
) -> Tuple[Dict[Any, Dict[str, Any]], Dict[Any, str], Dict[str, int]]:
    """Fetch trimmed requested items per ticket id, with a self-invalidating cache.

    Returns ``(by_ticket, errors, stats)`` where ``by_ticket[tid]`` is
    ``{"items": [...], "maybe_truncated": bool}``.

    Cache entries are keyed ``f"{ticket_id}:{updated_at}"`` inside a single
    blob, so editing a ticket invalidates just its own entry without waiting
    for the TTL, and a follow-up question about a different catalog item costs
    no API calls at all. Custom fields are never cached — they are the bulky
    part — so asking for them forces a live fetch.
    """
    blob: Dict[str, Any] = read_cache(REQUESTED_ITEMS_KEY) or {}
    by_ticket: Dict[Any, Dict[str, Any]] = {}
    errors: Dict[Any, str] = {}
    stats = {"from_cache": 0, "fetched": 0}

    misses: List[Dict[str, Any]] = []
    for t in tickets:
        hit = None if include_custom_fields else blob.get(f"{t.get('id')}:{t.get('updated_at')}")
        if hit is not None:
            by_ticket[t.get("id")] = hit
            stats["from_cache"] += 1
        else:
            misses.append(t)

    if misses:
        results = await fetch_json_bounded(
            [f"tickets/{t.get('id')}/requested_items" for t in misses],
            concurrency=concurrency,
        )
        for t, res in zip(misses, results):
            tid = t.get("id")
            if isinstance(res, BaseException):
                errors[tid] = str(res)
                continue
            raw = res.get("requested_items", []) if isinstance(res, dict) else res
            if not isinstance(raw, list):
                raw = []
            entry = {
                "items": [_trim_item(i, include_custom_fields) for i in raw],
                # A full page suggests the sub-endpoint paginated. Flagging it
                # is free; chasing it would cost another request per ticket.
                "maybe_truncated": len(raw) >= _ITEMS_PER_TICKET_PAGE,
            }
            by_ticket[tid] = entry
            stats["fetched"] += 1
            if not include_custom_fields:
                blob[f"{tid}:{t.get('updated_at')}"] = entry

        if not include_custom_fields:
            if len(blob) > _ITEM_CACHE_MAX_ENTRIES:
                # dicts preserve insertion order, so the tail is the newest.
                blob = dict(list(blob.items())[-_ITEM_CACHE_MAX_ENTRIES:])
            write_cache(REQUESTED_ITEMS_KEY, blob)

    return by_ticket, errors, stats


async def _scan_requested_items(
    *,
    query: str,
    workspace_id: Optional[int],
    selectors: Optional[List[Union[int, str]]],
    match_items: str,
    min_distinct_items: Optional[int],
    max_distinct_items: Optional[int],
    max_scan: int,
    opts: Dict[str, Any],
) -> Dict[str, Any]:
    """Find tickets by their requested catalog items.

    Prefilter with *query*, keep the ticket types that can hold requested
    items, fan out for each one's items, then apply the item predicates.
    """
    notes: List[str] = []
    warnings: List[str] = []

    mode = (match_items or "any").lower().strip()
    if mode not in ("any", "all"):
        return {"error": f"match_items must be 'any' or 'all', got {match_items!r}"}

    scan_max = max_scan if isinstance(max_scan, int) and max_scan > 0 else _SCAN_MAX_DEFAULT
    if scan_max > _SCAN_MAX_CEILING:
        notes.append(f"max_scan clamped from {scan_max} to {_SCAN_MAX_CEILING}.")
        scan_max = _SCAN_MAX_CEILING

    try:
        concurrency = int(opts.get("concurrency", _SCAN_CONCURRENCY_DEFAULT))
    except (TypeError, ValueError):
        concurrency = _SCAN_CONCURRENCY_DEFAULT
    if not 1 <= concurrency <= _SCAN_CONCURRENCY_MAX:
        notes.append(f"concurrency clamped into 1..{_SCAN_CONCURRENCY_MAX}.")
        concurrency = min(max(1, concurrency), _SCAN_CONCURRENCY_MAX)

    include_custom_fields = bool(opts.get("include_custom_fields", False))
    include_non_srs = bool(opts.get("include_non_service_requests", False))

    # ── 1. resolve item selectors ──────────────────────────────────────
    groups = [
        (selectors or [], None),
        (_coerce_selectors(opts.get("item_ids")) or [], "id"),
        (_coerce_selectors(opts.get("item_names")) or [], "name"),
    ]
    resolved: List[Dict[str, Any]] = []
    catalog_source = None
    if any(sels for sels, _ in groups):
        catalog = await fetch_service_items()
        catalog_items = catalog.get("items") or []
        catalog_source = catalog.get("source")
        if not catalog_items:
            notes.append(
                "Catalog index unavailable, so name selectors degrade to matching "
                "service_item_name on each ticket's items (unverified): "
                f"{catalog.get('error', 'empty index')}"
            )
        # Only the per-selector entries matter downstream: each carries its own
        # display_ids + terms, which is what match_items="all" tests against.
        merged: Dict[str, List[Any]] = {"resolved": [], "unmatched": [], "notes": []}
        for sels, force in groups:
            if not sels:
                continue
            r = resolve_item_selectors(catalog_items, sels, force=force)
            for key in merged:
                merged[key].extend(r[key])

        if merged["unmatched"]:
            # Fail before spending a request per ticket: a typo is cheap to fix
            # and a silently dropped selector is very easy to miss in a list.
            return {
                "success": False,
                "error": "Some item selectors matched no catalog item — nothing was "
                         "scanned. Fix or remove them and re-run.",
                "unmatched": merged["unmatched"],
                "hint": "read_service_catalog(action='list_item_index') lists every "
                        "item's display_id and name.",
            }
        resolved = merged["resolved"]
        notes.extend(merged["notes"])

    # ── 2. server-side prefilter ───────────────────────────────────────
    tickets, pmeta = await _filter_tickets_all_pages(query, workspace_id, scan_max)
    if pmeta.get("error") and not tickets:
        return {"success": False, "error": pmeta["error"]}

    # ── 3. narrow to types that can hold requested items ───────────────
    if include_non_srs:
        candidates, scanned_types = tickets, "all"
    elif tickets and not any(t.get("type") is not None for t in tickets):
        # The response stopped carrying `type`. Returning zero matches here
        # would read as "nothing requests that item", which is far worse than
        # scanning everything and saying so.
        candidates, scanned_types = tickets, "all"
        notes.append(
            "No ticket in the filter response carried a `type` field, so the "
            "Service-Request gate was disabled and every candidate was scanned."
        )
    else:
        candidates = [t for t in tickets if t.get("type") in _REQUESTED_ITEM_TYPES]
        scanned_types = sorted(_REQUESTED_ITEM_TYPES)
    skipped_by_type = len(tickets) - len(candidates)

    # ── 4. fan out for each candidate's requested items ────────────────
    by_ticket, fetch_errors, stats = await _requested_items_for(
        candidates, concurrency, include_custom_fields
    )

    # ── 5. apply the predicates ────────────────────────────────────────
    matches: List[Dict[str, Any]] = []
    histogram: Dict[Any, Dict[str, Any]] = {}
    partial_items = 0

    for t in candidates:
        entry = by_ticket.get(t.get("id"))
        if entry is None:
            continue  # fetch failed — surfaced in scan.errors
        items = entry.get("items") or []
        distinct = {i.get("service_item_id") for i in items
                    if i.get("service_item_id") is not None}

        if resolved:
            per_selector = [[i for i in items if _selector_matches(s, i)] for s in resolved]
            hits = sum(1 for group in per_selector if group)
            if hits == 0 or (mode == "all" and hits < len(resolved)):
                continue
            # Dedupe: one item can satisfy more than one selector, and
            # double-counting it would inflate the quantity rollup.
            seen_items: Set[Any] = set()
            matched_items = []
            for group in per_selector:
                for i in group:
                    marker = i.get("id", id(i))
                    if marker in seen_items:
                        continue
                    seen_items.add(marker)
                    matched_items.append(i)
        else:
            matched_items = items

        if min_distinct_items is not None and len(distinct) < min_distinct_items:
            continue
        if max_distinct_items is not None and len(distinct) > max_distinct_items:
            continue

        rollup = _rollup_items(matched_items)
        row = _trim(t, _TICKET_SUMMARY_FIELDS)
        row["distinct_item_count"] = len(distinct)
        row["line_item_count"] = len(items)
        row["matched_items"] = rollup
        row["all_item_ids"] = sorted(d for d in distinct if isinstance(d, int))
        if entry.get("maybe_truncated"):
            row["items_may_be_truncated"] = True
            partial_items += 1
        matches.append(row)

        for r in rollup:
            h = histogram.setdefault(r["service_item_id"], {
                "service_item_id": r["service_item_id"],
                "name": r["service_item_name"],
                "tickets": 0,
                "quantity": 0,
            })
            h["tickets"] += 1
            h["quantity"] += r["quantity"]

    # ── 6. report honestly on anything we capped or dropped ────────────
    if pmeta.get("truncated"):
        warnings.append(
            f"TRUNCATED: {pmeta.get('total')} tickets matched `{query}` but only "
            f"{len(tickets)} were scanned (max_scan={scan_max}). Narrow the query "
            f"or raise max_scan (ceiling {_SCAN_MAX_CEILING})."
        )
    if pmeta.get("error"):
        warnings.append(f"PARTIAL: {pmeta['error']}")
    if fetch_errors:
        msg = (f"PARTIAL: requested items could not be fetched for {len(fetch_errors)} "
               "ticket(s), which are therefore ABSENT from the results — this list is "
               "incomplete. See scan.errors.")
        # Match the status phrase, not a bare "429": the message embeds the
        # request URL, so a ticket id like 11429 would be a false positive.
        rate_limited = sum(1 for m in fetch_errors.values() if "429 Too Many Requests" in str(m))
        if rate_limited:
            msg += (f" {rate_limited} of them were rate-limited (429); Freshservice caps "
                    "requests per minute, so narrow `query`, lower payload.concurrency, "
                    "or wait a minute and re-run — tickets already fetched are cached.")
        warnings.append(msg)
    if partial_items:
        warnings.append(
            f"PARTIAL: {partial_items} ticket(s) returned a full page of requested "
            "items, so their item list may be incomplete (items_may_be_truncated)."
        )

    result: Dict[str, Any] = {
        "success": True,
        "criteria": {
            "query": query,
            "workspace_id": workspace_id,
            "match_items": mode if resolved else None,
            "resolved": [_trim(r, ("selector", "display_ids", "names", "matched_by"))
                         for r in resolved],
            "min_distinct_items": min_distinct_items,
            "max_distinct_items": max_distinct_items,
            "catalog_source": catalog_source,
            "scanned_types": scanned_types,
        },
        "matches": matches,
        "summary": {
            "matched_tickets": len(matches),
            "item_histogram": sorted(histogram.values(),
                                     key=lambda h: (-h["tickets"], -h["quantity"])),
        },
        "scan": {
            "prefilter_total": pmeta.get("total"),
            "prefilter_fetched": len(tickets),
            "prefilter_pages": pmeta.get("pages"),
            "skipped_by_type": skipped_by_type,
            "tickets_scanned": len(candidates),
            "items_from_cache": stats["from_cache"],
            "items_fetched": stats["fetched"],
            "truncated": bool(pmeta.get("truncated")),
            "truncation_reason": pmeta.get("truncation_reason"),
            "max_scan": scan_max,
            "concurrency": concurrency,
            "errors": _summarise_errors(fetch_errors),
            "notes": notes,
            "note": "Freshservice cannot filter by requested item server-side, so "
                    "these results come from a client-side scan of the tickets "
                    "matching `query`.",
        },
    }
    if warnings:
        result["warning"] = " ".join(warnings)
    return result


def register_tickets_tools(mcp) -> None:  # noqa: C901
    """Register ticket-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  ticket + sub-entities — consolidated read/manage split             #
    # ------------------------------------------------------------------ #
    _READ_TICKET = {
        # parent
        "get", "list", "filter", "get_fields",
        # conversations
        "list_conversations",
        # tasks
        "list_tasks", "get_task",
        # time entries
        "list_time_entries", "get_time_entry",
        # approvals
        "list_approvals", "get_approval",
    }
    _WRITE_TICKET = {
        # parent
        "create", "update", "delete",
        # conversations
        "reply", "add_note", "update_conversation",
        # tasks
        "add_task", "update_task", "delete_task",
        # time entries
        "add_time_entry", "update_time_entry", "delete_time_entry",
        # approvals
        "add_approval", "approve", "reject", "remind",
        # requested items (Service Requests only)
        "add_requested_item",
    }

    async def _ticket_handler(  # noqa: C901
        action: str,
        # parent
        ticket_id: Optional[int],
        subject: Optional[str],
        description: Optional[str],
        priority: Optional[Union[int, str]],
        status: Optional[Union[int, str]],
        email: Optional[str],
        requester_id: Optional[int],
        ticket_fields: Optional[Dict[str, Any]],
        query: Optional[str],
        page: int,
        per_page: int,
        workspace_id: Optional[int],
        # sub-entity ids
        conversation_id: Optional[int],
        task_id: Optional[int],
        time_entry_id: Optional[int],
        approval_id: Optional[int],
        # shared sub-entity fields
        body: Optional[str],
        title: Optional[str],
        time_spent: Optional[str],
        approver_id: Optional[int],
        # long-tail
        payload: Optional[Dict[str, Any]],
        # read-only extras
        include_image_content: bool = False,
        items: Any = None,
        match_items: str = "any",
        min_distinct_items: Optional[int] = None,
        max_distinct_items: Optional[int] = None,
        max_scan: int = _SCAN_MAX_DEFAULT,
    ) -> Any:
        pl: Dict[str, Any] = coerce_payload(payload)

        # ── parent ticket ──────────────────────────────────────────────
        if action == "get_fields":
            try:
                resp = await api_get("ticket_form_fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "fetch ticket fields")

        if action == "list":
            err = _validate_pagination(page, per_page)
            if err:
                return err
            try:
                resp = await api_get("tickets", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "tickets": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list tickets")

        if action == "filter":
            if not query:
                return {"error": "query is required for filter action"}

            selectors = _coerce_selectors(items)
            if (selectors is not None or min_distinct_items is not None
                    or max_distinct_items is not None
                    or pl.get("item_ids") or pl.get("item_names")):
                # Requested-item filtering: a client-side scan, not a passthrough.
                return await _scan_requested_items(
                    query=query,
                    workspace_id=workspace_id,
                    selectors=selectors,
                    match_items=match_items,
                    min_distinct_items=min_distinct_items,
                    max_distinct_items=max_distinct_items,
                    max_scan=max_scan,
                    opts=pl,
                )

            # Plain passthrough: one request, Freshservice's own response body.
            encoded_query = urllib.parse.quote(f'"{query}"')
            url = f"tickets/filter?query={encoded_query}&page={page}"
            if workspace_id is not None:
                url += f"&workspace_id={workspace_id}"
            try:
                resp = await api_get(url)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter tickets")

        if action == "get":
            if not ticket_id:
                return {"error": "ticket_id is required for get action"}
            # Native Freshservice include params: stats + requester come back
            # embedded in the main response, saving a round trip.
            try:
                resp = await api_get(
                    f"tickets/{ticket_id}",
                    params={"include": "stats,requester"},
                )
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "get ticket")

            # Parallel sub-fetches for tasks and approvals (always),
            # and requested_items for Service Requests.
            jobs: Dict[str, str] = {
                "tasks": f"tickets/{ticket_id}/tasks",
                "approvals": f"tickets/{ticket_id}/approvals",
            }
            if result.get("ticket", {}).get("type") == "Service Request":
                jobs["requested_items"] = f"tickets/{ticket_id}/requested_items"
            result.update(await gather_enrichments(jobs))

            if include_image_content:
                refs: List[Dict[str, Any]] = []
                ticket_obj = result.get("ticket") or {}
                for r in _collect_image_refs(ticket_obj):
                    refs.append({**r, "origin": "ticket"})
                images, manifest, skipped = await _gather_images(refs)
                result["image_content"] = {
                    "fetched": manifest,
                    "skipped": skipped,
                    "note": "Image bytes attached as separate image content blocks in this response.",
                }
                if images:
                    return [result, *images]
            return result

        if action == "create":
            if not subject or not description:
                return {"error": "subject and description are required for create"}
            if not email and not requester_id:
                return {"error": "Either email or requester_id must be provided"}
            try:
                source_val = int(pl["source"]) if "source" in pl else TicketSource.PORTAL.value
                priority_val = int(priority) if priority else TicketPriority.LOW.value
                status_val = int(status) if status else TicketStatus.OPEN.value
            except (ValueError, TypeError):
                return {"error": "Invalid value for source, priority, or status"}
            data: Dict[str, Any] = {
                "subject": subject,
                "description": description,
                "source": source_val,
                "priority": priority_val,
                "status": status_val,
            }
            if email:
                data["email"] = email
            if requester_id:
                data["requester_id"] = requester_id
            if "custom_fields" in pl:
                data["custom_fields"] = pl["custom_fields"]
            try:
                resp = await api_post("tickets", json=data)
                resp.raise_for_status()
                return {"success": True, "ticket": resp.json()}
            except Exception as e:
                return handle_error(e, "create ticket")

        if action == "update":
            if not ticket_id:
                return {"error": "ticket_id is required for update"}
            fields = dict(ticket_fields) if ticket_fields else {}
            if priority is not None:
                fields["priority"] = int(priority)
            if status is not None:
                fields["status"] = int(status)
            if subject is not None:
                fields["subject"] = subject
            if description is not None:
                fields["description"] = description
            if "custom_fields" in pl:
                fields["custom_fields"] = pl["custom_fields"]
            if not fields:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"tickets/{ticket_id}", json=fields)
                resp.raise_for_status()
                return {"success": True, "ticket": resp.json()}
            except Exception as e:
                return handle_error(e, "update ticket")

        if action == "delete":
            if not ticket_id:
                return {"error": "ticket_id is required for delete"}
            try:
                resp = await api_delete(f"tickets/{ticket_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Ticket deleted successfully"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete ticket")

        # ── conversations ──────────────────────────────────────────────
        if action == "list_conversations":
            if not ticket_id:
                return {"error": "ticket_id required for list_conversations"}
            try:
                resp = await api_get(f"tickets/{ticket_id}/conversations")
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                return handle_error(e, "list conversations")

            if include_image_content:
                refs: List[Dict[str, Any]] = []
                convs = result.get("conversations") if isinstance(result, dict) else None
                # The endpoint occasionally returns a bare list on some tenants;
                # handle both shapes defensively.
                iterable = convs if isinstance(convs, list) else (result if isinstance(result, list) else [])
                for conv in iterable:
                    if not isinstance(conv, dict):
                        continue
                    origin = f"conversation:{conv.get('id')}"
                    for r in _collect_image_refs(conv):
                        refs.append({**r, "origin": origin})
                images, manifest, skipped = await _gather_images(refs)
                if not isinstance(result, dict):
                    result = {"conversations": result}
                result["image_content"] = {
                    "fetched": manifest,
                    "skipped": skipped,
                    "note": "Image bytes attached as separate image content blocks in this response.",
                }
                if images:
                    return [result, *images]
            return result

        if action == "reply":
            if not ticket_id or not body:
                return {"error": "ticket_id and body required for reply"}
            # from_email is only sent when explicitly provided. Letting
            # Freshservice fall back to the account's default support email
            # avoids HTTP 400 from passing a non-configured address.
            attachment_paths = pl.get("attachments")
            if isinstance(attachment_paths, str):
                attachment_paths = [attachment_paths]
            try:
                if attachment_paths:
                    files = build_attachment_parts(attachment_paths)
                    # httpx 0.28+ requires data as a dict (not list of tuples)
                    # when combined with files=; list values become repeated
                    # keys in the multipart body.
                    form: Dict[str, Any] = {"body": body.strip()}
                    if "from_email" in pl:
                        form["from_email"] = str(pl["from_email"])
                    if "user_id" in pl:
                        form["user_id"] = str(pl["user_id"])
                    cc = pl.get("cc_emails") or []
                    if cc:
                        form["cc_emails[]"] = [str(e) for e in cc]
                    bcc = pl.get("bcc_emails") or []
                    if bcc:
                        form["bcc_emails[]"] = [str(e) for e in bcc]
                    resp = await api_post_multipart(
                        f"tickets/{ticket_id}/reply", data=form, files=files,
                    )
                else:
                    data = {"body": body.strip()}
                    for k in ("from_email", "user_id", "cc_emails", "bcc_emails"):
                        if k in pl:
                            data[k] = pl[k]
                    resp = await api_post(f"tickets/{ticket_id}/reply", json=data)
                resp.raise_for_status()
                return resp.json()
            except FileNotFoundError as e:
                return {"error": str(e)}
            except Exception as e:
                return handle_error(e, "reply to ticket")

        if action == "add_note":
            if not ticket_id or not body:
                return {"error": "ticket_id and body required for add_note"}
            attachment_paths = pl.get("attachments")
            if isinstance(attachment_paths, str):
                attachment_paths = [attachment_paths]
            try:
                if attachment_paths:
                    files = build_attachment_parts(attachment_paths)
                    form: Dict[str, Any] = {"body": body}
                    if "private" in pl:
                        form["private"] = str(bool(pl["private"])).lower()
                    resp = await api_post_multipart(
                        f"tickets/{ticket_id}/notes", data=form, files=files,
                    )
                else:
                    data = {"body": body}
                    if "private" in pl:
                        data["private"] = pl["private"]
                    resp = await api_post(f"tickets/{ticket_id}/notes", json=data)
                resp.raise_for_status()
                return resp.json()
            except FileNotFoundError as e:
                return {"error": str(e)}
            except Exception as e:
                return handle_error(e, "add ticket note")

        if action == "update_conversation":
            if not conversation_id or not body:
                return {"error": "conversation_id and body required for update_conversation"}
            try:
                resp = await api_put(f"conversations/{conversation_id}", json={"body": body})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "update conversation")

        # ── tasks ──────────────────────────────────────────────────────
        if action in {"list_tasks", "get_task", "add_task", "update_task", "delete_task"}:
            if not ticket_id:
                return {"error": "ticket_id required for task actions"}
            base = f"tickets/{ticket_id}/tasks"

            if action == "list_tasks":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list ticket tasks")

            if action == "get_task":
                if not task_id:
                    return {"error": "task_id required for get_task"}
                try:
                    resp = await api_get(f"{base}/{task_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get ticket task")

            if action == "add_task":
                if not title:
                    return {"error": "title required for add_task"}
                data = {"title": title}
                if description is not None:
                    data["description"] = description
                if status is not None:
                    data["status"] = int(status)
                for k in ("due_date", "notify_before", "group_id", "agent_id"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "add ticket task")

            if action == "update_task":
                if not task_id:
                    return {"error": "task_id required for update_task"}
                data = {}
                if title is not None:
                    data["title"] = title
                if description is not None:
                    data["description"] = description
                if status is not None:
                    data["status"] = int(status)
                for k in ("due_date", "notify_before", "group_id", "agent_id"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_put(f"{base}/{task_id}", json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "update ticket task")

            if action == "delete_task":
                if not task_id:
                    return {"error": "task_id required for delete_task"}
                try:
                    resp = await api_delete(f"{base}/{task_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": "Task deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete ticket task")

        # ── time entries ───────────────────────────────────────────────
        if action in {"list_time_entries", "get_time_entry", "add_time_entry",
                       "update_time_entry", "delete_time_entry"}:
            if not ticket_id:
                return {"error": "ticket_id required for time entry actions"}
            base = f"tickets/{ticket_id}/time_entries"

            if action == "list_time_entries":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list time entries")

            if action == "get_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for get_time_entry"}
                try:
                    resp = await api_get(f"{base}/{time_entry_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get time entry")

            if action == "add_time_entry":
                te_agent_id = pl.get("te_agent_id")
                if not te_agent_id or not time_spent:
                    return {"error": "payload.te_agent_id and time_spent required for add_time_entry"}
                data = {"agent_id": te_agent_id, "time_spent": time_spent}
                if body is not None:
                    data["note"] = body
                for k in ("executed_at", "task_id", "billable", "timer_running"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "create time entry")

            if action == "update_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for update_time_entry"}
                data = {}
                if time_spent is not None:
                    data["time_spent"] = time_spent
                if body is not None:
                    data["note"] = body
                for k in ("executed_at", "billable", "timer_running"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_put(f"{base}/{time_entry_id}", json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "update time entry")

            if action == "delete_time_entry":
                if not time_entry_id:
                    return {"error": "time_entry_id required for delete_time_entry"}
                try:
                    resp = await api_delete(f"{base}/{time_entry_id}")
                    if resp.status_code == 204:
                        return {"success": True, "message": "Time entry deleted"}
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "delete time entry")

        # ── approvals ──────────────────────────────────────────────────
        if action in {"list_approvals", "get_approval", "add_approval",
                       "approve", "reject", "remind"}:
            if not ticket_id:
                return {"error": "ticket_id required for approval actions"}
            base = f"tickets/{ticket_id}/approvals"

            if action == "list_approvals":
                try:
                    resp = await api_get(base)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "list ticket approvals")

            if action == "get_approval":
                if not approval_id:
                    return {"error": "approval_id required for get_approval"}
                try:
                    resp = await api_get(f"{base}/{approval_id}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "get ticket approval")

            if action == "add_approval":
                if not approver_id:
                    return {"error": "approver_id required for add_approval"}
                data = {"approver_id": approver_id}
                for k in ("approval_type", "email_content"):
                    if k in pl:
                        data[k] = pl[k]
                try:
                    resp = await api_post(base, json=data)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return handle_error(e, "create ticket approval")

            if action in {"approve", "reject", "remind"}:
                if not approval_id:
                    return {"error": f"approval_id required for {action}"}
                try:
                    resp = await api_put(f"{base}/{approval_id}/{action}")
                    resp.raise_for_status()
                    return {"success": True, "message": f"Approval {action} sent"}
                except Exception as e:
                    return handle_error(e, f"{action} ticket approval")

        # ── requested items (Service Requests only) ────────────────────
        if action == "add_requested_item":
            if not ticket_id:
                return {"error": "ticket_id required for add_requested_item"}
            item_id = pl.get("item_id")
            if not item_id:
                return {"error": "payload.item_id required for add_requested_item"}
            data: Dict[str, Any] = {"item_id": item_id}
            if "custom_fields" in pl:
                data["custom_fields"] = pl["custom_fields"]
            try:
                resp = await api_post(f"tickets/{ticket_id}/requested_items", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "add requested item")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_ticket(
        action: Optional[str] = None,
        ticket_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        approval_id: Optional[int] = None,
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
        workspace_id: Optional[int] = None,
        include_image_content: bool = False,
        items: Optional[Union[List[Union[int, str]], str, int]] = None,
        match_items: str = "any",
        min_distinct_items: Optional[int] = None,
        max_distinct_items: Optional[int] = None,
        max_scan: int = _SCAN_MAX_DEFAULT,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Read Freshservice tickets and their sub-entities.

        Actions:
          get, list, filter, get_fields,
          list_conversations,
          list_tasks, get_task,
          list_time_entries, get_time_entry,
          list_approvals, get_approval

        Synonyms accepted: view/show/read → get, find/search → filter,
        index/all → list.

        Required per action:
          get: ticket_id
          filter: query
          list_conversations / list_tasks / list_time_entries / list_approvals: ticket_id
          get_task: ticket_id, task_id
          get_time_entry: ticket_id, time_entry_id
          get_approval: ticket_id, approval_id

        Optional: page, per_page (list/filter), workspace_id (filter),
          items / match_items / min_distinct_items / max_distinct_items /
          max_scan / payload (filter, requested-item mode).

        Default action: if not provided, inferred from params —
          ticket_id → get, items or a distinct-item bound → filter,
          query → filter, otherwise list.

        Notes:
          - get auto-enriches with stats + requester (native ?include= on
            the main fetch), plus parallel sub-fetches for tasks, approvals,
            and (on Service Requests) requested_items with their
            custom_fields. Failed sub-fetches surface as _<key>_warning.
          - get_fields returns ticket form fields incl. instance-specific
            status/priority choices — call before filter.
          - filter: query is URL-encoded and wrapped in double quotes.
            Use 'agent_id' (not 'responder_id'). Logical ops: AND, OR.
            Relational: :>, :<. Null: field:null.
            Example: "agent_id:120002355359 AND status:2"
            Filterable fields do NOT include ticket type — narrow by status,
            priority, impact, urgency, tag, due_by, fr_due_by, created_at,
            agent_id, group_id, requester_id, department_id, category,
            sub_category, item_category or cf_* only.
          - filter by REQUESTED CATALOG ITEM — answers "which tickets request
            item 34?" Pass any of items / min_distinct_items /
            max_distinct_items alongside query and the response changes to
            {criteria, matches, summary, scan}; without them, filter stays a
            plain one-request passthrough of Freshservice's own body.
              items: list of catalog display_ids and/or item-name substrings,
                mixed freely — e.g. [34, 39, "Headphones"]. A display_id is
                the SMALL number shown in the catalog, not the 75000xxxxxxx
                internal id. Names are matched case-insensitively; a name
                matching several items includes all of them. An unmatched
                selector is a hard error (with suggestions) BEFORE any
                scanning, so fix typos and re-run.
              match_items: "any" (default, OR) or "all" (ticket must request
                every listed item).
              min_distinct_items / max_distinct_items: bound the number of
                DISTINCT catalog items on the ticket — min_distinct_items=2
                finds multi-item Service Requests.
              Omit items and pass min_distinct_items=0 to report the items on
                every scanned ticket without filtering by item at all.
              summary.item_histogram totals tickets and quantity per item, so
                "how many open tickets for each of these items?" needs one call.
              max_scan (default 200, ceiling 500): cap on tickets whose items
                are fetched.
              payload: item_ids / item_names (force a selector to be read as
                an id or a name), concurrency (default 5, max 10),
                include_custom_fields (default False — item custom_fields are
                very large), include_non_service_requests (default False).
            COST: Freshservice cannot filter by requested item server-side, so
            this runs your query, keeps the Service Requests (only they can
            hold catalog items), then fetches requested_items once per
            candidate. Make query as narrow as you can. Results are capped,
            never silently — ALWAYS check the top-level "warning" and
            scan.truncated before telling the user a list is complete.
          - include_image_content (default False): only honored by ``get``
            and ``list_conversations``. When True, downloads image
            attachments and inline-pasted screenshots from the ticket
            description (``get``) or each conversation body
            (``list_conversations``) and returns them alongside the JSON as
            MCP image content blocks. A ``image_content`` field on the JSON
            lists what was fetched and what was skipped (with reasons).
            Off by default because base64-encoded images bloat the response
            and slow the model down — opt in only when the screenshots
            matter. Caps: 5 MB / image, 20 MB total, 20 images per call.
        """
        action = normalize_action(action, _READ_TICKET)
        if not action:
            # Smart default: infer from which params the caller supplied.
            # Item params are checked before query, since a requested-item
            # scan supplies both.
            if ticket_id:
                action = "get"
            elif (items is not None or min_distinct_items is not None
                    or max_distinct_items is not None or query):
                action = "filter"
            else:
                action = "list"
        err = reject_unless_in(action, _READ_TICKET, "read_ticket", "manage_ticket")
        if err:
            return err
        return await _ticket_handler(
            action,
            ticket_id=ticket_id,
            subject=None, description=None, priority=None, status=None,
            email=None, requester_id=None, ticket_fields=None,
            query=query, page=page, per_page=per_page, workspace_id=workspace_id,
            conversation_id=None, task_id=task_id,
            time_entry_id=time_entry_id, approval_id=approval_id,
            body=None, title=None, time_spent=None, approver_id=None,
            payload=payload,
            include_image_content=include_image_content,
            items=items, match_items=match_items,
            min_distinct_items=min_distinct_items,
            max_distinct_items=max_distinct_items,
            max_scan=max_scan,
        )

    @mcp.tool()
    async def manage_ticket(
        action: str,
        ticket_id: Optional[int] = None,
        # parent ticket fields
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[Union[int, str]] = None,
        status: Optional[Union[int, str]] = None,
        email: Optional[str] = None,
        requester_id: Optional[int] = None,
        ticket_fields: Optional[Dict[str, Any]] = None,
        # sub-entity ids
        conversation_id: Optional[int] = None,
        task_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        approval_id: Optional[int] = None,
        # shared sub-entity fields
        body: Optional[str] = None,
        title: Optional[str] = None,
        time_spent: Optional[str] = None,
        approver_id: Optional[int] = None,
        # long-tail
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on tickets and their sub-entities.

        Actions:
          Ticket: create, update, delete
          Conversation: reply, add_note, update_conversation
          Task: add_task, update_task, delete_task
          Time entry: add_time_entry, update_time_entry, delete_time_entry
          Approval: add_approval, approve, reject, remind
          Requested item (Service Requests only): add_requested_item

        Required per action:
          create: subject, description, (email OR requester_id)
          update / delete: ticket_id
          reply / add_note: ticket_id, body
          update_conversation: conversation_id, body
          add_task: ticket_id, title
          update_task / delete_task: ticket_id, task_id
          add_time_entry: ticket_id, time_spent, payload.te_agent_id
          update_time_entry / delete_time_entry: ticket_id, time_entry_id
          add_approval: ticket_id, approver_id
          approve / reject / remind: ticket_id, approval_id
          add_requested_item: ticket_id, payload.item_id

        Optional fields:
          - priority: 1=Low,2=Medium,3=High,4=Urgent (ticket/task)
          - status: ticket 2=Open,3=Pending,4=Resolved,5=Closed; task 1=Open,2=InProgress,3=Done
          - ticket_fields: dict of bulk-update fields
          - title: task title
          - body: conversation/note body, or time-entry note

        payload (long-tail keys) — pass only those that apply to the action:
          - source: ticket source enum (create)
          - custom_fields: dict of custom field values (create/update)
          - from_email, user_id, cc_emails, bcc_emails (reply)
              from_email is OPTIONAL: omit it and Freshservice uses the
              account's default support email. Only pass it if it is a
              configured support address — an arbitrary value will 400.
          - private (add_note): True = internal/agent-only note
          - attachments (reply/add_note): local file path string or list
              of paths. Sent as multipart/form-data. Freshservice caps:
              15 files / 40 MB total.
          - due_date, notify_before, group_id, agent_id (add_task/update_task)
          - te_agent_id (add_time_entry — REQUIRED in payload)
          - executed_at, task_id, billable, timer_running (time entries)
          - approval_type, email_content (add_approval)
          - item_id (add_requested_item — REQUIRED in payload): catalog
              item id to attach to the existing Service Request
          - custom_fields (add_requested_item): dict of catalog-item
              custom fields keyed by their API names
        """
        action = normalize_action(action, _WRITE_TICKET)
        err = reject_unless_in(action, _WRITE_TICKET, "manage_ticket", "read_ticket")
        if err:
            return err
        return await _ticket_handler(
            action,
            ticket_id=ticket_id,
            subject=subject, description=description, priority=priority, status=status,
            email=email, requester_id=requester_id, ticket_fields=ticket_fields,
            query=None, page=1, per_page=30, workspace_id=None,
            conversation_id=conversation_id, task_id=task_id,
            time_entry_id=time_entry_id, approval_id=approval_id,
            body=body, title=title, time_spent=time_spent, approver_id=approver_id,
            payload=payload,
        )

    # ------------------------------------------------------------------ #
    #  service_catalog — read/manage split (sibling to tickets)           #
    # ------------------------------------------------------------------ #
    _READ_SERVICE_CATALOG = {"list_items", "list_item_index"}
    _WRITE_SERVICE_CATALOG = {"place_request"}

    async def _service_catalog_handler(
        action: str,
        display_id: Optional[int],
        email: Optional[str],
        requested_for: Optional[str],
        quantity: int,
        page: int,
        per_page: int,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        if action == "list_item_index":
            result = await fetch_service_items(force_refresh=force_refresh)
            if "items" not in result:
                return result  # error dict from handle_error
            return {"success": True, "total": len(result["items"]), **result}

        if action == "list_items":
            err = _validate_pagination(page, per_page)
            if err:
                return err
            all_items: List[Any] = []
            current_page = page
            try:
                while True:
                    resp = await api_get("service_catalog/items", params={"page": current_page, "per_page": per_page})
                    resp.raise_for_status()
                    # Flatten the per-page envelope: appending resp.json()
                    # handed callers a list of {"service_items": [...]} pages.
                    all_items.extend(resp.json().get("service_items", []))
                    pagination_info = parse_link_header(resp.headers.get("Link", ""))
                    if not pagination_info.get("next"):
                        break
                    current_page = pagination_info["next"]
                return {"success": True, "total": len(all_items), "items": all_items}
            except Exception as e:
                return handle_error(e, "list service items")

        if action == "place_request":
            if not display_id or not email:
                return {"error": "display_id and email required for place_request"}
            data: Dict[str, Any] = {"email": email, "quantity": quantity}
            if requested_for:
                data["requested_for"] = requested_for
            try:
                resp = await api_post(f"service_catalog/items/{display_id}/place_request", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "place service request")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_service_catalog(
        action: str,
        page: int = 1,
        per_page: int = 30,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Read Freshservice service catalog.

        Actions:
          list_item_index — compact {display_id, id, name, item_type, deleted}
            for every catalog item, cached locally for an hour. Prefer this:
            it is a few KB where list_items is ~100 KB of HTML descriptions
            and field definitions. Use it to map an item name to the small
            display_id that requested_items and place_request expect.
          list_items — every catalog item in full, all pages, uncached.

        Optional: page, per_page (list_items), force_refresh (list_item_index).

        Notes:
          - To fetch the requested items on an existing Service Request, use
            ``read_ticket`` with ``action='get'`` — it embeds the ticket's
            ``requested_items`` for SR-type tickets.
          - To find which tickets request a given item, use ``read_ticket``
            with ``action='filter'`` and ``items=[...]``.
        """
        action = normalize_action(action, _READ_SERVICE_CATALOG)
        err = reject_unless_in(action, _READ_SERVICE_CATALOG, "read_service_catalog", "manage_service_catalog")
        if err:
            return err
        return await _service_catalog_handler(
            action, display_id=None, email=None, requested_for=None,
            quantity=1, page=page, per_page=per_page, force_refresh=force_refresh,
        )

    @mcp.tool()
    async def manage_service_catalog(
        action: str,
        display_id: Optional[int] = None,
        email: Optional[str] = None,
        requested_for: Optional[str] = None,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice service catalog.

        Actions: place_request
        Required per action:
          place_request: display_id, email
        Optional: requested_for (target user email), quantity (default 1).

        Note: to add a catalog item to an *existing* Service Request, use
        ``manage_ticket`` with ``action='add_requested_item'``.
        """
        action = normalize_action(action, _WRITE_SERVICE_CATALOG)
        err = reject_unless_in(action, _WRITE_SERVICE_CATALOG, "manage_service_catalog", "read_service_catalog")
        if err:
            return err
        return await _service_catalog_handler(
            action, display_id=display_id, email=email,
            requested_for=requested_for, quantity=quantity, page=1, per_page=30,
        )
