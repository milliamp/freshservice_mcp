"""Freshservice MCP — Custom Objects tools.

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_custom_object / manage_custom_object
      Reads: list_objects, get_object, list_records, get_record
      Writes: create_record, update_record, delete_record
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
from ._split import normalize_action, reject_unless_in


def register_custom_objects_tools(mcp) -> None:
    """Register custom object tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  custom_object — read/manage split                                  #
    # ------------------------------------------------------------------ #
    _READ_CUSTOM_OBJECT = {"list_objects", "get_object", "list_records", "get_record"}
    _WRITE_CUSTOM_OBJECT = {"create_record", "update_record", "delete_record"}

    async def _custom_object_handler(
        action: str,
        type_id: Optional[int],
        record_id: Optional[int],
        data: Optional[Dict[str, Any]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
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

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_custom_object(
        action: str,
        type_id: Optional[int] = None,
        record_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice custom objects and their records.

        Actions: list_objects, get_object, list_records, get_record

        Required per action:
          get_object / list_records: type_id
          get_record: type_id, record_id

        Optional: page, per_page (list_objects, list_records).
        """
        action = normalize_action(action, _READ_CUSTOM_OBJECT)
        err = reject_unless_in(action, _READ_CUSTOM_OBJECT, "read_custom_object", "manage_custom_object")
        if err:
            return err
        return await _custom_object_handler(action, type_id, record_id, None, page, per_page)

    @mcp.tool()
    async def manage_custom_object(
        action: str,
        type_id: Optional[int] = None,
        record_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice custom object records.

        Actions: create_record, update_record, delete_record

        Required per action:
          create_record: type_id, data
          update_record: type_id, record_id, data
          delete_record: type_id, record_id
        """
        action = normalize_action(action, _WRITE_CUSTOM_OBJECT)
        err = reject_unless_in(action, _WRITE_CUSTOM_OBJECT, "manage_custom_object", "read_custom_object")
        if err:
            return err
        return await _custom_object_handler(action, type_id, record_id, data, page=1, per_page=30)
