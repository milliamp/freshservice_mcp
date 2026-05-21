"""Freshservice MCP — Locations tools.

Exposes 1 tool:
  - manage_location — CRUD + list
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


def register_locations_tools(mcp) -> None:
    """Register location-related tools on *mcp*."""

    @mcp.tool()
    async def manage_location(
        action: str,
        location_id: Optional[int] = None,
        name: Optional[str] = None,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        parent_location_id: Optional[int] = None,
        primary_contact_id: Optional[int] = None,
        address: Optional[Dict[str, str]] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice locations.

        Args:
            action: One of 'create', 'update', 'delete', 'get', 'list'
            location_id: Required for get, update, delete
            name: Location name (create - REQUIRED)
            contact_name: Contact person name
            email: Contact email
            phone: Contact phone number
            parent_location_id: Parent location ID for hierarchy
            primary_contact_id: Primary contact user ID
            address: Address dict with keys: line1, line2, city, state, country, zipcode
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = action.lower().strip()

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("locations", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "locations": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list locations")

        # ---------- get ----------
        if action == "get":
            if not location_id:
                return {"error": "location_id required for get"}
            try:
                resp = await api_get(f"locations/{location_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get location")

        # ---------- create ----------
        if action == "create":
            if not name:
                return {"error": "name is required for create"}
            data: Dict[str, Any] = {"name": name}
            for k, v in [("contact_name", contact_name), ("email", email),
                         ("phone", phone), ("parent_location_id", parent_location_id),
                         ("primary_contact_id", primary_contact_id)]:
                if v is not None:
                    data[k] = v
            if address:
                data["address"] = address
            try:
                resp = await api_post("locations", json=data)
                resp.raise_for_status()
                return {"success": True, "location": resp.json()}
            except Exception as e:
                return handle_error(e, "create location")

        # ---------- update ----------
        if action == "update":
            if not location_id:
                return {"error": "location_id required for update"}
            update_data: Dict[str, Any] = {}
            for k, v in [("name", name), ("contact_name", contact_name),
                         ("email", email), ("phone", phone),
                         ("parent_location_id", parent_location_id),
                         ("primary_contact_id", primary_contact_id)]:
                if v is not None:
                    update_data[k] = v
            if address:
                update_data["address"] = address
            if not update_data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"locations/{location_id}", json=update_data)
                resp.raise_for_status()
                return {"success": True, "location": resp.json()}
            except Exception as e:
                return handle_error(e, "update location")

        # ---------- delete ----------
        if action == "delete":
            if not location_id:
                return {"error": "location_id required for delete"}
            try:
                resp = await api_delete(f"locations/{location_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Location deleted"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete location")

        return {"error": f"Unknown action '{action}'. Valid: create, update, delete, get, list"}
