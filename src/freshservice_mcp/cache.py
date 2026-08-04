"""Freshservice MCP — Two-level (memory + disk) TTL cache.

Extracted from ``discovery.py`` so any module can share one cache without
reaching for another module's privates. Used for slow-changing reference data:
form-field definitions, asset types, the service-catalog index, and the
per-ticket requested-items index.

Configured by ``FRESHSERVICE_CACHE_DIR`` and ``FRESHSERVICE_CACHE_TTL``.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

CACHE_DIR = Path(os.getenv("FRESHSERVICE_CACHE_DIR", Path.home() / ".cache" / "freshservice_mcp"))
CACHE_TTL = int(os.getenv("FRESHSERVICE_CACHE_TTL", 3600))  # seconds – default 1 h

# Well-known keys, declared here so one module can invalidate another's cache
# by name (clear_field_cache clears both of these).
CATALOG_INDEX_KEY = "service_items_index"
REQUESTED_ITEMS_KEY = "requested_items_by_ticket"

# In-memory tier, in front of the on-disk tier.
_mem_cache: Dict[str, Dict[str, Any]] = {}


def cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def read_cache(key: str) -> Optional[Any]:
    """Return cached data if still within the TTL, else None."""
    # 1) in-memory
    if key in _mem_cache:
        entry = _mem_cache[key]
        if time.time() - entry["ts"] < CACHE_TTL:
            return entry["data"]
        del _mem_cache[key]

    # 2) on-disk
    p = cache_path(key)
    if p.exists():
        try:
            raw = json.loads(p.read_text())
            if time.time() - raw["ts"] < CACHE_TTL:
                _mem_cache[key] = raw  # promote to memory
                return raw["data"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return None


def write_cache(key: str, data: Any) -> None:
    entry = {"ts": time.time(), "data": data}
    _mem_cache[key] = entry
    try:
        cache_path(key).write_text(json.dumps(entry, default=str))
    except OSError:
        pass  # non-fatal — memory cache still works


def invalidate_cache(key: Optional[str] = None) -> None:
    """Clear cache for *key*, or all caches if key is None."""
    if key is None:
        _mem_cache.clear()
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*.json"):
                f.unlink(missing_ok=True)
    else:
        _mem_cache.pop(key, None)
        cache_path(key).unlink(missing_ok=True)
