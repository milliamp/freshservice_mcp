"""Freshservice MCP — Reference-data discovery with TTL cache.

Provides tools that dynamically read slow-changing templates from the
Freshservice organisation (ticket fields, change fields, agent fields,
requester fields, asset types, the service-catalog item index …) and cache
them locally so we don't hammer the API on every invocation.
"""
import difflib
from typing import Any, Dict, List, Optional, Set, Union

from .cache import (
    CATALOG_INDEX_KEY,
    REQUESTED_ITEMS_KEY,
    invalidate_cache,
    read_cache,
    write_cache,
)
from .http_client import api_get, handle_error, parse_link_header

# Back-compat aliases for this module's existing call sites.
_read_cache = read_cache
_write_cache = write_cache


def _cache_key_for(entity_type: str) -> str:
    """Map a user-facing entity name to its cache key."""
    return {
        "asset_type": "asset_types",
        "service_catalog": CATALOG_INDEX_KEY,
        "requested_items": REQUESTED_ITEMS_KEY,
    }.get(entity_type, f"fields_{entity_type}")


# ---------------------------------------------------------------------------
# Entity → API path mapping
# ---------------------------------------------------------------------------
_FIELD_ENDPOINTS: Dict[str, str] = {
    "ticket": "ticket_form_fields",
    "change": "change_form_fields",
    "agent": "agent_fields",
    "requester": "requester_fields",
    "problem": "problem_form_fields",
    "release": "release_form_fields",
    "department": "department_fields",
}


async def _fetch_fields(entity_type: str) -> Dict[str, Any]:
    """Fetch the form-field definitions from Freshservice API."""
    endpoint = _FIELD_ENDPOINTS.get(entity_type)
    if not endpoint:
        return {"error": f"Unknown entity type '{entity_type}'. Valid types: {list(_FIELD_ENDPOINTS.keys())}"}

    cache_key = f"fields_{entity_type}"
    cached = _read_cache(cache_key)
    if cached is not None:
        return {"source": "cache", "fields": cached}

    try:
        resp = await api_get(endpoint)
        resp.raise_for_status()
        data = resp.json()
        _write_cache(cache_key, data)
        return {"source": "api", "fields": data}
    except Exception as e:
        return handle_error(e, f"fetch {entity_type} fields")


async def _fetch_asset_types() -> Dict[str, Any]:
    """Fetch all asset types (paginated) and cache them."""
    cache_key = "asset_types"
    cached = _read_cache(cache_key)
    if cached is not None:
        return {"source": "cache", "asset_types": cached}

    all_types = []
    page = 1
    try:
        while True:
            resp = await api_get("asset_types", params={"page": page, "per_page": 100})
            resp.raise_for_status()
            data = resp.json()
            types = data.get("asset_types", [])
            if not types:
                break
            all_types.extend(types)
            page += 1
    except Exception as e:
        return handle_error(e, "fetch asset types")

    _write_cache(cache_key, all_types)
    return {"source": "api", "asset_types": all_types}


# ---------------------------------------------------------------------------
# Service-catalog item index + selector resolution
#
# Lives here because this module already owns the TTL cache and the
# paginate-then-cache pattern. Consumed by read_ticket's requested-item scan
# (which needs name → display_id) and by read_service_catalog list_item_index.
# ---------------------------------------------------------------------------
_CATALOG_MAX_PAGES = 50  # backstop against a pagination loop that never ends


async def fetch_service_items(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch every service-catalog item as a COMPACT index, TTL-cached.

    Returns ``{"source": "cache"|"api", "items": [{display_id, id, name,
    item_type, deleted}]}``. The raw catalog items carry HTML descriptions and
    full field definitions (~100 KB for 85 items); this keeps only what's
    needed to map between an item's small ``display_id`` and its name.
    """
    if force_refresh:
        invalidate_cache(CATALOG_INDEX_KEY)
    cached = _read_cache(CATALOG_INDEX_KEY)
    if cached is not None:
        return {"source": "cache", "items": cached}

    items: List[Dict[str, Any]] = []
    page = 1
    try:
        while page <= _CATALOG_MAX_PAGES:
            resp = await api_get("service_catalog/items", params={"page": page, "per_page": 100})
            resp.raise_for_status()
            batch = resp.json().get("service_items", [])
            if not batch:
                break
            items.extend(
                {
                    "display_id": it.get("display_id"),
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "item_type": it.get("item_type"),
                    "deleted": it.get("deleted", False),
                }
                for it in batch
            )
            # Trust the Link header rather than len(batch) < per_page: some
            # endpoints silently cap per_page, and a short page would then be
            # mistaken for the last one.
            nxt = parse_link_header(resp.headers.get("Link", "")).get("next")
            if not nxt:
                break
            page = nxt
    except Exception as e:
        return handle_error(e, "fetch service catalog items")

    _write_cache(CATALOG_INDEX_KEY, items)
    return {"source": "api", "items": items}


def resolve_item_selectors(
    items: List[Dict[str, Any]],
    selectors: List[Union[int, str]],
    force: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a MIXED list of catalog ``display_id``s and name substrings.

    Pure/sync. ``items`` is the index from :func:`fetch_service_items` (pass
    ``[]`` when the catalog is unavailable — every selector then degrades to a
    name-substring term matched against ``service_item_name`` on the wire).

    By default each selector is classified by shape: all-digits means a
    ``display_id``, anything else is a name. ``force="id"`` / ``force="name"``
    overrides that, for the rare catalog item whose name is all digits.

    Each entry in ``resolved`` carries both ``display_ids`` and ``terms`` so
    the caller can test a whole selector against a ticket — which is what
    ``match_items="all"`` needs. Returns::

        {"display_ids": {int,...}, "name_terms": [str,...],
         "resolved": [{selector, display_ids, terms, names, matched_by}],
         "unmatched": [{selector, suggestions}], "notes": [str,...]}
    """
    catalog = [(it.get("name") or "", it.get("display_id")) for it in items
               if it.get("display_id") is not None]
    catalog_names = [n for n, _ in catalog]

    display_ids: Set[int] = set()
    name_terms: List[str] = []
    resolved: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    notes: List[str] = []

    for sel in selectors:
        # bool is an int subclass — exclude it before the numeric branch.
        is_numeric = (isinstance(sel, int) and not isinstance(sel, bool)) or (
            isinstance(sel, str) and sel.strip().isdigit()
        )
        if force == "name":
            is_numeric = False
        elif force == "id" and not is_numeric:
            unmatched.append({
                "selector": sel,
                "reason": "payload.item_ids entries must be numeric display_ids",
                "suggestions": [],
            })
            continue
        if is_numeric:
            did = int(sel)
            display_ids.add(did)
            hit_names = [n for n, d in catalog if d == did]
            resolved.append({
                "selector": sel, "display_ids": [did], "terms": [],
                "names": hit_names, "matched_by": "display_id",
            })
            if catalog and not hit_names:
                notes.append(
                    f"display_id {did} is not in the catalog index "
                    "(deleted or newly added) — scanning for it anyway."
                )
            continue

        term = str(sel).strip()
        if not term:
            continue
        low = term.lower()
        exact = [(n, d) for n, d in catalog if n.lower() == low]
        hits = exact or [(n, d) for n, d in catalog if low in n.lower()]
        if hits:
            for _, d in hits:
                display_ids.add(d)
            name_terms.append(low)
            resolved.append({
                "selector": sel,
                "display_ids": sorted({d for _, d in hits}),
                # Keep the name term alive alongside the resolved ids: it
                # rescues an item added since the index was cached.
                "terms": [low],
                "names": [n for n, _ in hits],
                "matched_by": "exact_name" if exact else "name_substring",
            })
            if len(hits) > 1:
                notes.append(
                    f"'{term}' matched {len(hits)} catalog items "
                    f"({', '.join(n for n, _ in hits)}) — all are included."
                )
        elif not catalog:
            # Catalog unavailable: degrade to a wire-name match rather than
            # failing the whole query.
            name_terms.append(low)
            resolved.append({
                "selector": sel, "display_ids": [], "terms": [low],
                "names": [], "matched_by": "name_substring_unverified",
            })
        else:
            unmatched.append({
                "selector": sel,
                "suggestions": difflib.get_close_matches(term, catalog_names, n=5, cutoff=0.5),
            })

    return {
        "display_ids": display_ids,
        "name_terms": name_terms,
        "resolved": resolved,
        "unmatched": unmatched,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Tool registration (called from server.py)
# ---------------------------------------------------------------------------
def register_discovery_tools(mcp) -> None:
    """Register discovery-related tools on the MCP server."""

    @mcp.tool()
    async def discover_form_fields(
        entity_type: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Discover the form-field definitions for an entity type in your Freshservice organisation.

        Returns the list of fields (name, label, type, required, choices…) that
        your org has configured.  Results are cached locally for 1 hour.

        Args:
            entity_type: One of 'ticket', 'change', 'agent', 'requester', 'asset_type'
            force_refresh: Set to true to bypass the cache and re-fetch from Freshservice
        """
        if force_refresh:
            invalidate_cache(_cache_key_for(entity_type))

        if entity_type == "asset_type":
            return await _fetch_asset_types()
        return await _fetch_fields(entity_type)

    @mcp.tool()
    async def clear_field_cache(entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Clear locally cached Freshservice reference data.

        Args:
            entity_type: Specific cache to clear — a form-field entity
                ('ticket', 'change', 'agent', 'requester', 'asset_type'),
                'service_catalog' (the item name/display_id index) or
                'requested_items' (the per-ticket requested-items index used
                by read_ticket's item filter). Omit to clear all.
        """
        if entity_type:
            invalidate_cache(_cache_key_for(entity_type))
            return {"success": True, "message": f"Cache cleared for '{entity_type}'"}
        invalidate_cache()
        return {"success": True, "message": "All reference-data caches cleared"}
