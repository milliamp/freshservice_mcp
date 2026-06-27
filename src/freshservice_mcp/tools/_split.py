"""Action-whitelist guard used by the read_/manage_ tool split.

Each consolidated tool is now exposed as a pair: ``read_X`` (read-only
actions) and ``manage_X`` (write actions). Both call the same private
handler; the guard below validates that the caller's ``action`` is allowed
for the wrapper they invoked, so MCP clients can grant read-only or
read-write permissions independently.
"""
from typing import Any, Dict, Iterable, Optional


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


def normalize_action(action: Optional[str]) -> str:
    """Lowercase, strip, and map common synonyms to canonical names.

    Returns an empty string if ``action`` is None/non-str so callers can
    then apply their own smart-default logic.
    """
    if not isinstance(action, str):
        return ""
    a = action.lower().strip()
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
