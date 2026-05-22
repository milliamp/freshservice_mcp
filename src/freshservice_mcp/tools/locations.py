"""Freshservice MCP — Location tools.

Exposes 1 tool:
  • manage_location  — CRUD + list + filter locations
"""
from typing import Any, Dict, Optional

from ..http_client import api_delete, api_get, api_post, api_put, handle_error


def register_locations_tools(mcp) -> None:
    """Register location tools on *mcp*."""

    @mcp.tool()
    async def manage_location(
        action: str,
        location_id: Optional[int] = None,
        # creation / update fields
        name: Optional[str] = None,
        line1: Optional[str] = None,
        line2: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        zipcode: Optional[str] = None,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        parent_location_id: Optional[int] = None,
        # filter / pagination
        query: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Manage Freshservice locations.

        Args:
            action: One of 'list', 'get', 'create', 'update', 'delete', 'filter'.
            location_id: Location ID (required for get/update/delete).
            name: Location name (required for create).
            line1/line2/city/state/country/zipcode: Address fields.
            contact_name: Contact person name.
            email: Contact email.
            phone: Contact phone.
            parent_location_id: Parent location ID for hierarchical locations.
            query: Filter query for 'filter' action (e.g. "name:'New York'").
            page/per_page: Pagination.
        """
        action = action.lower().strip()

        if action == "list":
            try:
                resp = await api_get("locations", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list locations")

        if action == "get":
            if not location_id:
                return {"error": "location_id required for get"}
            try:
                resp = await api_get(f"locations/{location_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get location")

        if action == "create":
            if not name:
                return {"error": "name required for create"}
            data: Dict[str, Any] = {"name": name}
            addr: Dict[str, str] = {}
            for k, v in [("line1", line1), ("line2", line2), ("city", city),
                         ("state", state), ("country", country), ("zipcode", zipcode)]:
                if v:
                    addr[k] = v
            if addr:
                data["address"] = addr
            for k, v in [("contact_name", contact_name), ("email", email),
                         ("phone", phone), ("parent_location_id", parent_location_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("locations", json=data)
                resp.raise_for_status()
                return {"success": True, "location": resp.json()}
            except Exception as e:
                return handle_error(e, "create location")

        if action == "update":
            if not location_id:
                return {"error": "location_id required for update"}
            data = {}
            if name:
                data["name"] = name
            addr = {}
            for k, v in [("line1", line1), ("line2", line2), ("city", city),
                         ("state", state), ("country", country), ("zipcode", zipcode)]:
                if v is not None:
                    addr[k] = v
            if addr:
                data["address"] = addr
            for k, v in [("contact_name", contact_name), ("email", email),
                         ("phone", phone), ("parent_location_id", parent_location_id)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_put(f"locations/{location_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "location": resp.json()}
            except Exception as e:
                return handle_error(e, "update location")

        if action == "delete":
            if not location_id:
                return {"error": "location_id required for delete"}
            try:
                resp = await api_delete(f"locations/{location_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": f"Location {location_id} deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete location")

        if action == "filter":
            if not query:
                return {"error": "query required for filter (e.g. \"name:'New York'\")"}
            try:
                resp = await api_get(
                    "locations",
                    params={"query": f'"{query}"', "page": page, "per_page": per_page},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter locations")

        return {
            "error": f"Unknown action '{action}'. Valid: list, get, create, update, delete, filter"
        }
