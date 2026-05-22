"""Action-whitelist guard used by the read_/manage_ tool split.

Each consolidated tool is now exposed as a pair: ``read_X`` (read-only
actions) and ``manage_X`` (write actions). Both call the same private
handler; the guard below validates that the caller's ``action`` is allowed
for the wrapper they invoked, so MCP clients can grant read-only or
read-write permissions independently.
"""
from typing import Any, Dict, Iterable, Optional


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
