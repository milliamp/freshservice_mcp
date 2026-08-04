"""Freshservice MCP — Assets tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently. Tools that have no write
actions are exposed only as read_*.

Tools:
  • read_asset / manage_asset                       — list/get/search/filter/
                                                       get_types/get_type/
                                                       get_type_fields vs
                                                       create/update/delete/
                                                       delete_permanently/
                                                       restore/move/create_type
  • read_asset_details                              — components, assignment
                                                       history, requests,
                                                       contracts (read only)
  • read_asset_relationship /
    manage_asset_relationship                       — list_for_asset/list_all/
                                                       get/get_types/job_status
                                                       vs create/delete
"""
import json
from typing import Any, Dict, List, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    handle_error,
    parse_link_header,
)
from ._split import normalize_action, reject_unless_in


def register_assets_tools(mcp) -> None:
    """Register asset-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  asset — read/manage split                                          #
    # ------------------------------------------------------------------ #
    _READ_ASSET = {
        "list", "get", "search", "filter",
        "get_types", "get_type", "get_type_fields",
    }
    _WRITE_ASSET = {
        "create", "update", "delete", "delete_permanently",
        "restore", "move", "create_type",
    }

    async def _asset_handler(
        action: str,
        # identifiers
        display_id: Optional[int],
        asset_type_id: Optional[int],
        # create / update fields
        name: Optional[str],
        asset_tag: Optional[str],
        impact: Optional[str],
        usage_type: Optional[str],
        description: Optional[str],
        user_id: Optional[int],
        location_id: Optional[int],
        department_id: Optional[int],
        agent_id: Optional[int],
        group_id: Optional[int],
        assigned_on: Optional[str],
        workspace_id: Optional[int],
        type_fields: Optional[Dict[str, Any]],
        asset_fields: Optional[Dict[str, Any]],
        # search / filter / list
        search_query: Optional[str],
        filter_query: Optional[str],
        include: Optional[str],
        order_by: Optional[str],
        order_type: Optional[str],
        trashed: bool,
        page: int,
        per_page: int,
        # create_type fields
        parent_asset_type_id: Optional[int],
        visible: Optional[bool],
    ) -> Dict[str, Any]:
        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            if include:
                params["include"] = include
            if order_by:
                params["order_by"] = order_by
            if order_type:
                params["order_type"] = order_type
            if trashed:
                params["trashed"] = "true"
            if workspace_id is not None:
                params["workspace_id"] = workspace_id
            try:
                resp = await api_get("assets", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "assets": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list assets")

        # ---------- get ----------
        if action == "get":
            if not display_id:
                return {"error": "display_id required for get"}
            params = {}
            if include:
                params["include"] = include
            try:
                resp = await api_get(f"assets/{display_id}", params=params or None)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get asset")

        # ---------- search ----------
        if action == "search":
            if not search_query:
                return {"error": "search_query required for search"}
            params: Dict[str, Any] = {
                "query": f'"{search_query}"',
                "page": page,
            }
            if trashed:
                params["trashed"] = "true"
            try:
                resp = await api_get("assets", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "search assets")

        # ---------- filter ----------
        if action == "filter":
            if not filter_query:
                return {"error": "filter_query required for filter"}
            # Freshservice filter expects the value wrapped in double-quotes,
            # e.g. filter="asset_type_id:50000039936"
            # Strip any existing outer quotes the caller may have added.
            fq = filter_query.strip('"')
            params: Dict[str, Any] = {
                "filter": f'"{fq}"',
                "page": page,
            }
            if include:
                params["include"] = include
            try:
                resp = await api_get("assets", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "filter assets")

        # ---------- create ----------
        if action == "create":
            if not name or not asset_type_id:
                return {"error": "name and asset_type_id are required for create"}
            # Validate enums
            valid_impacts = {"low", "medium", "high"}
            valid_usage = {"permanent", "loaner"}
            imp = (impact or "low").lower()
            usg = (usage_type or "permanent").lower()
            if imp not in valid_impacts:
                return {"error": f"impact must be one of {valid_impacts}"}
            if usg not in valid_usage:
                return {"error": f"usage_type must be one of {valid_usage}"}

            data: Dict[str, Any] = {
                "name": name,
                "asset_type_id": asset_type_id,
                "impact": imp,
                "usage_type": usg,
            }
            for k, v in [("asset_tag", asset_tag), ("description", description),
                         ("user_id", user_id), ("location_id", location_id),
                         ("department_id", department_id), ("agent_id", agent_id),
                         ("group_id", group_id), ("assigned_on", assigned_on),
                         ("workspace_id", workspace_id)]:
                if v is not None:
                    data[k] = v
            if type_fields:
                data["type_fields"] = type_fields
            try:
                resp = await api_post("assets", json=data)
                resp.raise_for_status()
                return {"success": True, "asset": resp.json()}
            except Exception as e:
                return handle_error(e, "create asset")

        # ---------- update ----------
        if action == "update":
            if not display_id:
                return {"error": "display_id required for update"}
            fields = asset_fields or {}
            # Allow explicit params to override
            for k, v in [("name", name), ("asset_tag", asset_tag),
                         ("impact", impact), ("usage_type", usage_type),
                         ("description", description), ("user_id", user_id),
                         ("location_id", location_id), ("department_id", department_id),
                         ("agent_id", agent_id), ("group_id", group_id),
                         ("assigned_on", assigned_on)]:
                if v is not None:
                    fields[k] = v
            if type_fields:
                fields["type_fields"] = type_fields
            if not fields:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"assets/{display_id}", json=fields)
                resp.raise_for_status()
                return {"success": True, "asset": resp.json()}
            except Exception as e:
                return handle_error(e, "update asset")

        # ---------- delete ----------
        if action == "delete":
            if not display_id:
                return {"error": "display_id required for delete"}
            try:
                resp = await api_delete(f"assets/{display_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Asset moved to trash"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete asset")

        # ---------- delete_permanently ----------
        if action == "delete_permanently":
            if not display_id:
                return {"error": "display_id required for delete_permanently"}
            try:
                resp = await api_put(f"assets/{display_id}/delete_forever")
                if resp.status_code == 204:
                    return {"success": True, "message": "Asset permanently deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "permanently delete asset")

        # ---------- restore ----------
        if action == "restore":
            if not display_id:
                return {"error": "display_id required for restore"}
            try:
                resp = await api_put(f"assets/{display_id}/restore")
                resp.raise_for_status()
                return {"success": True, "message": "Asset restored"}
            except Exception as e:
                return handle_error(e, "restore asset")

        # ---------- move ----------
        if action == "move":
            if not display_id or workspace_id is None:
                return {"error": "display_id and workspace_id required for move"}
            data = {"workspace_id": workspace_id}
            if agent_id is not None:
                data["agent_id"] = agent_id
            if group_id is not None:
                data["group_id"] = group_id
            try:
                resp = await api_put(f"assets/{display_id}/move_workspace", json=data)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "move asset")

        # ---------- get_types ----------
        if action == "get_types":
            params = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("asset_types", params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list asset types")

        # ---------- get_type ----------
        if action == "get_type":
            if not asset_type_id:
                return {"error": "asset_type_id required for get_type"}
            try:
                resp = await api_get(f"asset_types/{asset_type_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get asset type")

        # ---------- create_type ----------
        if action == "create_type":
            if not name:
                return {"error": "name is required for create_type"}
            # Do NOT send 'visible'. It comes back on a read but the create
            # endpoint rejects it outright ("Unexpected/invalid field in
            # request"), so including it 400s every call.
            data: Dict[str, Any] = {"name": name}
            if description:
                data["description"] = description
            if parent_asset_type_id:
                data["parent_asset_type_id"] = parent_asset_type_id
            try:
                resp = await api_post("asset_types", json=data)
                resp.raise_for_status()
                result: Dict[str, Any] = {"success": True, "asset_type": resp.json()}
                # Accepted-but-ignored rather than rejected: callers primed by
                # the old signature still succeed, and the note tells them why
                # their argument had no effect.
                if visible is not None:
                    result["warning"] = (
                        "'visible' was ignored — Freshservice does not accept it when "
                        "creating an asset type. Adjust visibility in the Freshservice "
                        "admin UI instead."
                    )
                return result
            except Exception as e:
                return handle_error(e, "create asset type")

        # ---------- get_type_fields ----------
        if action == "get_type_fields":
            if not asset_type_id:
                return {"error": "asset_type_id required for get_type_fields"}
            try:
                resp = await api_get(f"asset_types/{asset_type_id}/fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get asset type fields")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_asset(
        action: Optional[str] = None,
        display_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        search_query: Optional[str] = None,
        filter_query: Optional[str] = None,
        include: Optional[str] = None,
        order_by: Optional[str] = None,
        order_type: Optional[str] = None,
        trashed: bool = False,
        workspace_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice assets and asset types.

        Actions: list, get, search, filter, get_types, get_type, get_type_fields

        Synonyms accepted: view/show/read → get, find → filter,
        index/all → list.

        Required per action:
          get: display_id
          search: search_query (name/tag/serial)
          filter: filter_query (e.g. "asset_type_id:50000039936")
          get_type / get_type_fields: asset_type_id

        Optional: include (e.g. 'type_fields'), order_by, order_type,
        trashed, workspace_id, page, per_page.

        Default action: if not provided, inferred from params —
          display_id → get, search_query → search,
          filter_query → filter, asset_type_id → get_type, else list.
        """
        action = normalize_action(action, _READ_ASSET)
        if not action:
            if display_id:
                action = "get"
            elif search_query:
                action = "search"
            elif filter_query:
                action = "filter"
            elif asset_type_id:
                action = "get_type"
            else:
                action = "list"
        err = reject_unless_in(action, _READ_ASSET, "read_asset", "manage_asset")
        if err:
            return err
        return await _asset_handler(
            action,
            display_id=display_id, asset_type_id=asset_type_id,
            name=None, asset_tag=None, impact=None, usage_type=None,
            description=None, user_id=None, location_id=None,
            department_id=None, agent_id=None, group_id=None,
            assigned_on=None, workspace_id=workspace_id,
            type_fields=None, asset_fields=None,
            search_query=search_query, filter_query=filter_query,
            include=include, order_by=order_by, order_type=order_type,
            trashed=trashed, page=page, per_page=per_page,
            parent_asset_type_id=None, visible=None,
        )

    @mcp.tool()
    async def manage_asset(
        action: str,
        # identifiers
        display_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        # create / update fields
        name: Optional[str] = None,
        asset_tag: Optional[str] = None,
        impact: Optional[str] = None,
        usage_type: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
        location_id: Optional[int] = None,
        department_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        group_id: Optional[int] = None,
        assigned_on: Optional[str] = None,
        workspace_id: Optional[int] = None,
        type_fields: Optional[Dict[str, Any]] = None,
        asset_fields: Optional[Dict[str, Any]] = None,
        # create_type fields
        parent_asset_type_id: Optional[int] = None,
        visible: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice assets and asset types.

        Actions: create, update, delete, delete_permanently, restore, move,
          create_type

        Required per action:
          create: name, asset_type_id
          update / delete / delete_permanently / restore: display_id
          move: display_id, workspace_id
          create_type: name

        Optional fields:
          impact: low|medium|high (default low)
          usage_type: permanent|loaner (default permanent)
          asset_tag, description, user_id, location_id, department_id,
          agent_id, group_id, assigned_on, workspace_id, type_fields,
          asset_fields (update alternative payload),
          parent_asset_type_id, description (create_type).

        Note: 'visible' is not settable via the API — Freshservice rejects it
        on asset-type create. It is accepted here but ignored, and the
        response carries a warning saying so. Set visibility in the admin UI.
        """
        action = normalize_action(action, _WRITE_ASSET)
        err = reject_unless_in(action, _WRITE_ASSET, "manage_asset", "read_asset")
        if err:
            return err
        return await _asset_handler(
            action,
            display_id=display_id, asset_type_id=asset_type_id,
            name=name, asset_tag=asset_tag, impact=impact,
            usage_type=usage_type, description=description,
            user_id=user_id, location_id=location_id,
            department_id=department_id, agent_id=agent_id,
            group_id=group_id, assigned_on=assigned_on,
            workspace_id=workspace_id, type_fields=type_fields,
            asset_fields=asset_fields,
            search_query=None, filter_query=None, include=None,
            order_by=None, order_type=None, trashed=False,
            page=1, per_page=30,
            parent_asset_type_id=parent_asset_type_id, visible=visible,
        )

    # ------------------------------------------------------------------ #
    #  asset_details — read only                                          #
    # ------------------------------------------------------------------ #
    _READ_ASSET_DETAILS = {"components", "assignment_history", "requests", "contracts"}

    @mcp.tool()
    async def read_asset_details(
        action: str,
        display_id: int,
    ) -> Dict[str, Any]:
        """Retrieve asset sub-resources (read only).

        Args:
            action: 'components', 'assignment_history', 'requests', 'contracts'
            display_id: The asset display ID
        """
        action = normalize_action(action, _READ_ASSET_DETAILS)
        err = reject_unless_in(action, _READ_ASSET_DETAILS, "read_asset_details", "(no write counterpart)")
        if err:
            return err
        endpoints = {
            "components": "components",
            "assignment_history": "assignment-history",
            "requests": "requests",
            "contracts": "contracts",
        }
        try:
            resp = await api_get(f"assets/{display_id}/{endpoints[action]}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return handle_error(e, f"get asset {action}")

    # ------------------------------------------------------------------ #
    #  asset_relationship — read/manage split                             #
    # ------------------------------------------------------------------ #
    _READ_ASSET_RELATIONSHIP = {"list_for_asset", "list_all", "get", "get_types", "job_status"}
    _WRITE_ASSET_RELATIONSHIP = {"create", "delete"}

    async def _asset_relationship_handler(
        action: str,
        display_id: Optional[int],
        relationship_id: Optional[int],
        relationship_ids: Optional[List[int]],
        relationships: Optional[List[Dict[str, Any]]],
        job_id: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "list_for_asset":
            if not display_id:
                return {"error": "display_id required for list_for_asset"}
            try:
                resp = await api_get(f"assets/{display_id}/relationships")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list asset relationships")

        if action == "list_all":
            try:
                resp = await api_get("relationships", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "relationships": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                    },
                }
            except Exception as e:
                return handle_error(e, "list all relationships")

        if action == "get":
            if not relationship_id:
                return {"error": "relationship_id required for get"}
            try:
                resp = await api_get(f"relationships/{relationship_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get relationship")

        if action == "create":
            if not relationships:
                return {"error": "relationships list required for create"}
            # Guard: MCP tool params may arrive as a JSON string
            if isinstance(relationships, str):
                try:
                    relationships = json.loads(relationships)
                except json.JSONDecodeError:
                    return {"error": "relationships must be a JSON array of dicts"}
            if not isinstance(relationships, list):
                return {"error": "relationships must be a list of dicts"}
            try:
                payload = {"relationships": relationships}
                resp = await api_post("relationships/bulk-create", json=payload)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "create relationships")

        if action == "delete":
            if not relationship_ids:
                return {"error": "relationship_ids list required for delete"}
            # Guard: MCP tool params may arrive as a JSON string
            if isinstance(relationship_ids, str):
                try:
                    relationship_ids = json.loads(relationship_ids)
                except json.JSONDecodeError:
                    return {"error": "relationship_ids must be a JSON array of ints"}
            ids_str = ",".join(str(i) for i in relationship_ids)
            try:
                resp = await api_delete(f"relationships?ids={ids_str}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Relationships deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete relationships")

        if action == "get_types":
            try:
                resp = await api_get("relationship_types")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get relationship types")

        if action == "job_status":
            if not job_id:
                return {"error": "job_id required for job_status"}
            try:
                resp = await api_get(f"jobs/{job_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get job status")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_asset_relationship(
        action: str,
        display_id: Optional[int] = None,
        relationship_id: Optional[int] = None,
        job_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read asset relationships.

        Args:
            action: 'list_for_asset', 'list_all', 'get', 'get_types', 'job_status'
            display_id: Asset display ID (list_for_asset)
            relationship_id: Relationship ID (get)
            job_id: Job ID returned by async operations (job_status)
            page: Page number (list_all)
            per_page: Items per page (list_all)
        """
        action = normalize_action(action, _READ_ASSET_RELATIONSHIP)
        err = reject_unless_in(action, _READ_ASSET_RELATIONSHIP, "read_asset_relationship", "manage_asset_relationship")
        if err:
            return err
        return await _asset_relationship_handler(
            action,
            display_id=display_id, relationship_id=relationship_id,
            relationship_ids=None, relationships=None,
            job_id=job_id, page=page, per_page=per_page,
        )

    @mcp.tool()
    async def manage_asset_relationship(
        action: str,
        relationship_ids: Optional[List[int]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Write actions on asset relationships.

        Args:
            action: 'create', 'delete'
            relationship_ids: List of rel IDs to delete (delete)
            relationships: List of relationship dicts for bulk create (create).
                Each dict: {relationship_type_id, primary_id, primary_type,
                            secondary_id, secondary_type}
        """
        action = normalize_action(action, _WRITE_ASSET_RELATIONSHIP)
        err = reject_unless_in(action, _WRITE_ASSET_RELATIONSHIP, "manage_asset_relationship", "read_asset_relationship")
        if err:
            return err
        return await _asset_relationship_handler(
            action,
            display_id=None, relationship_id=None,
            relationship_ids=relationship_ids, relationships=relationships,
            job_id=None, page=1, per_page=30,
        )
