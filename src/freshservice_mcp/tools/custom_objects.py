"""Freshservice MCP — Custom Objects tools.

Exposes 1 tool:
  - manage_custom_object — list_objects, get_object, list_records, get_record,
                           create_record, update_record, delete_record
"""
from typing import Any, Dict, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    handle_error,
    parse_link_header,
)


def register_custom_objects_tools(mcp) -> None:
    """Register custom object tools on *mcp*."""

    @mcp.tool()
    async def manage_custom_object(
        action: str,
        type_id: Optional[int] = None,
        record_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice custom objects and their records.

        Args:
            action: One of 'list_objects', 'get_object', 'list_records', 'get_record',
                    'create_record', 'update_record', 'delete_record'
            type_id: Object type ID (required for all actions except list_objects)
            record_id: Record ID (required for get_record, update_record, delete_record)
            data: Record field data dict (create_record, update_record)
            page: Page number (list_objects, list_records)
            per_page: Items per page 1-100 (list_objects, list_records)
        """
        action = action.lower().strip()

        # ---------- list_objects ----------
        if action == "list_objects":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("objects", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "objects": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list custom objects")

        # ---------- get_object ----------
        if action == "get_object":
            if not type_id:
                return {"error": "type_id required for get_object"}
            try:
                resp = await api_get(f"objects/{type_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get custom object")

        # ---------- list_records ----------
        if action == "list_records":
            if not type_id:
                return {"error": "type_id required for list_records"}
            params = {"page": page, "per_page": per_page}
            try:
                resp = await api_get(f"objects/{type_id}/records", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "records": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list custom object records")

        # ---------- get_record ----------
        if action == "get_record":
            if not type_id or not record_id:
                return {"error": "type_id and record_id required for get_record"}
            try:
                resp = await api_get(f"objects/{type_id}/records/{record_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get custom object record")

        # ---------- create_record ----------
        if action == "create_record":
            if not type_id:
                return {"error": "type_id required for create_record"}
            if not data:
                return {"error": "data dict required for create_record"}
            try:
                resp = await api_post(f"objects/{type_id}/records", json=data)
                resp.raise_for_status()
                return {"success": True, "record": resp.json()}
            except Exception as e:
                return handle_error(e, "create custom object record")

        # ---------- update_record ----------
        if action == "update_record":
            if not type_id or not record_id:
                return {"error": "type_id and record_id required for update_record"}
            if not data:
                return {"error": "data dict required for update_record"}
            try:
                resp = await api_put(f"objects/{type_id}/records/{record_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "record": resp.json()}
            except Exception as e:
                return handle_error(e, "update custom object record")

        # ---------- delete_record ----------
        if action == "delete_record":
            if not type_id or not record_id:
                return {"error": "type_id and record_id required for delete_record"}
            try:
                resp = await api_delete(f"objects/{type_id}/records/{record_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Record deleted"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete custom object record")

        return {"error": f"Unknown action '{action}'. Valid: list_objects, get_object, list_records, get_record, create_record, update_record, delete_record"}
