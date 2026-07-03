"""Action-whitelist guard used by the read_/manage_ tool split.

Each consolidated tool is now exposed as a pair: ``read_X`` (read-only
actions) and ``manage_X`` (write actions). Both call the same private
handler; the guard below validates that the caller's ``action`` is allowed
for the wrapper they invoked, so MCP clients can grant read-only or
read-write permissions independently.
"""
import json
from typing import Any, Dict, Iterable, Optional


def coerce_payload(payload: Any) -> Dict[str, Any]:
    """Return a dict from ``payload``, tolerating JSON-string form.

    Some MCP clients serialize dict-typed arguments as JSON strings on the
    wire (observed live: ``payload='{"attachments": ["…"]}'``). This
    helper transparently parses that back to a dict; a plain dict passes
    through; anything else (or a malformed string) becomes an empty dict.
    """
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


# Common natural-language synonyms LLMs reach for when they don't know the
# canonical verb. Normalized at the wrapper layer so callers can use the
# verb they expect; the handler dispatch only ever sees the canonical name.
_SYNONYMS: Dict[str, str] = {
    # read aliases
    "view": "get",
    "show": "get",
    "read": "get",
    "fetch": "get",
    "retrieve": "get",
    "describe": "get",
    # list aliases
    "index": "list",
    "all": "list",
    "list_all": "list",
    "enumerate": "list",
    # filter aliases
    "find": "filter",
    "search": "filter",
    "query": "filter",
    # write aliases
    "add": "create",
    "new": "create",
    "modify": "update",
    "edit": "update",
    "patch": "update",
    "remove": "delete",
    "destroy": "delete",
}


def normalize_action(
    action: Optional[str],
    allowed: Optional[Iterable[str]] = None,
) -> str:
    """Lowercase, strip, and map common synonyms to canonical names.

    If ``allowed`` is provided and the input action is already canonical
    for that tool, the synonym table is skipped. This matters when a tool
    has both a canonical name AND its synonym as distinct actions — e.g.
    read_asset has both ``search`` (free-text) and ``filter`` (structured
    query), so a caller asking for ``search`` must NOT silently become
    ``filter``. Same for ``view`` on read_change_note (where ``view`` is
    the canonical action) and ``list_all`` on read_asset_relationship.

    Returns an empty string if ``action`` is None/non-str so callers can
    apply their own smart-default logic.
    """
    if not isinstance(action, str):
        return ""
    a = action.lower().strip()
    if allowed is not None and a in allowed:
        return a
    return _SYNONYMS.get(a, a)


def reject_unless_in(
    action: str,
    allowed: Iterable[str],
    tool_name: str,
    counterpart: str,
) -> Optional[Dict[str, Any]]:
    """Return an error dict if ``action`` is not in ``allowed``, else None."""
    if action not in allowed:
        return {
            "error": (
                f"{tool_name}: action '{action}' is not allowed here. "
                f"Allowed: {sorted(allowed)}. Use {counterpart} for the rest."
            )
        }
    return None
