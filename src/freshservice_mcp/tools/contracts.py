"""Freshservice MCP — Contracts tools.

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_contract / manage_contract — list/get/get_types/get_type/get_type_fields
                                       vs create/update/delete
"""
from typing import Any, Dict, List, Optional

from ..http_client import (
    api_delete,
    api_get,
    api_post,
    api_put,
    handle_error,
    parse_link_header,
)
from ._split import reject_unless_in


def register_contracts_tools(mcp) -> None:
    """Register contract-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  contract — read/manage split                                       #
    # ------------------------------------------------------------------ #
    _READ_CONTRACT = {"list", "get", "get_types", "get_type", "get_type_fields"}
    _WRITE_CONTRACT = {"create", "update", "delete"}

    async def _contract_handler(
        action: str,
        contract_id: Optional[int],
        contract_type_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        vendor_id: Optional[int],
        approver_id: Optional[int],
        start_date: Optional[str],
        end_date: Optional[str],
        cost: Optional[int],
        contract_number: Optional[str],
        auto_renew: Optional[bool],
        notify_expiry: Optional[bool],
        notify_before: Optional[int],
        visible_to_id: Optional[int],
        software_id: Optional[int],
        notify_to: Optional[List[str]],
        billing_cycle: Optional[str],
        associated_asset_ids: Optional[List[int]],
        item_cost_details: Optional[List[Dict[str, Any]]],
        custom_fields: Optional[Dict[str, Any]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        # ---------- get_types ----------
        if action == "get_types":
            try:
                resp = await api_get("contract_types")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "list contract types")

        # ---------- get_type ----------
        if action == "get_type":
            if not contract_type_id:
                return {"error": "contract_type_id required for get_type"}
            try:
                resp = await api_get(f"contract_types/{contract_type_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get contract type")

        # ---------- get_type_fields ----------
        if action == "get_type_fields":
            if not contract_type_id:
                return {"error": "contract_type_id required for get_type_fields"}
            try:
                resp = await api_get(f"contract_types/{contract_type_id}/fields")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get contract type fields")

        # ---------- list ----------
        if action == "list":
            params: Dict[str, Any] = {"page": page, "per_page": per_page}
            try:
                resp = await api_get("contracts", params=params)
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "contracts": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list contracts")

        # ---------- get ----------
        if action == "get":
            if not contract_id:
                return {"error": "contract_id required for get"}
            try:
                resp = await api_get(f"contracts/{contract_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get contract")

        # ---------- create ----------
        if action == "create":
            missing = []
            for field_name, field_val in [("name", name), ("vendor_id", vendor_id),
                                           ("approver_id", approver_id),
                                           ("start_date", start_date),
                                           ("end_date", end_date), ("cost", cost),
                                           ("contract_number", contract_number),
                                           ("contract_type_id", contract_type_id)]:
                if field_val is None:
                    missing.append(field_name)
            if missing:
                return {"error": f"Required fields missing for create: {', '.join(missing)}"}

            data: Dict[str, Any] = {
                "name": name,
                "vendor_id": vendor_id,
                "approver_id": approver_id,
                "start_date": start_date,
                "end_date": end_date,
                "cost": cost,
                "contract_number": contract_number,
                "contract_type_id": contract_type_id,
            }
            for k, v in [("description", description), ("visible_to_id", visible_to_id),
                         ("software_id", software_id), ("billing_cycle", billing_cycle),
                         ("notify_before", notify_before)]:
                if v is not None:
                    data[k] = v
            if auto_renew is not None:
                data["auto_renew"] = auto_renew
            if notify_expiry is not None:
                data["notify_expiry"] = notify_expiry
            if notify_to:
                data["notify_to"] = notify_to
            if associated_asset_ids:
                data["associated_asset_ids"] = associated_asset_ids
            if item_cost_details:
                data["item_cost_details"] = item_cost_details
            if custom_fields:
                data["custom_fields"] = custom_fields

            try:
                resp = await api_post("contracts", json=data)
                resp.raise_for_status()
                return {"success": True, "contract": resp.json()}
            except Exception as e:
                return handle_error(e, "create contract")

        # ---------- update ----------
        if action == "update":
            if not contract_id:
                return {"error": "contract_id required for update"}
            update_data: Dict[str, Any] = {}
            for k, v in [("name", name), ("description", description),
                         ("vendor_id", vendor_id), ("approver_id", approver_id),
                         ("start_date", start_date), ("end_date", end_date),
                         ("cost", cost), ("contract_number", contract_number),
                         ("contract_type_id", contract_type_id),
                         ("visible_to_id", visible_to_id),
                         ("software_id", software_id),
                         ("billing_cycle", billing_cycle),
                         ("notify_before", notify_before)]:
                if v is not None:
                    update_data[k] = v
            if auto_renew is not None:
                update_data["auto_renew"] = auto_renew
            if notify_expiry is not None:
                update_data["notify_expiry"] = notify_expiry
            if notify_to is not None:
                update_data["notify_to"] = notify_to
            if associated_asset_ids is not None:
                update_data["associated_asset_ids"] = associated_asset_ids
            if item_cost_details is not None:
                update_data["item_cost_details"] = item_cost_details
            if custom_fields:
                update_data["custom_fields"] = custom_fields
            if not update_data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"contracts/{contract_id}", json=update_data)
                resp.raise_for_status()
                return {"success": True, "contract": resp.json()}
            except Exception as e:
                return handle_error(e, "update contract")

        # ---------- delete ----------
        if action == "delete":
            if not contract_id:
                return {"error": "contract_id required for delete"}
            try:
                resp = await api_delete(f"contracts/{contract_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Contract deleted"}
                return {"error": f"Unexpected status {resp.status_code}"}
            except Exception as e:
                return handle_error(e, "delete contract")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_contract(
        action: str,
        contract_id: Optional[int] = None,
        contract_type_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice contracts.

        Args:
            action: One of 'list', 'get', 'get_types', 'get_type', 'get_type_fields'
            contract_id: Required for get
            contract_type_id: Required for get_type, get_type_fields.
                1=Lease, 2=Maintenance, 3=Software License, 4=Warranty.
            page: Page number (list)
            per_page: Items per page 1-100 (list)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_CONTRACT, "read_contract", "manage_contract")
        if err:
            return err
        return await _contract_handler(
            action, contract_id, contract_type_id, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, None, None,
            None, None, page, per_page,
        )

    @mcp.tool()
    async def manage_contract(
        action: str,
        contract_id: Optional[int] = None,
        contract_type_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        vendor_id: Optional[int] = None,
        approver_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cost: Optional[int] = None,
        contract_number: Optional[str] = None,
        auto_renew: Optional[bool] = None,
        notify_expiry: Optional[bool] = None,
        notify_before: Optional[int] = None,
        visible_to_id: Optional[int] = None,
        software_id: Optional[int] = None,
        notify_to: Optional[List[str]] = None,
        billing_cycle: Optional[str] = None,
        associated_asset_ids: Optional[List[int]] = None,
        item_cost_details: Optional[List[Dict[str, Any]]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice contracts.

        Args:
            action: One of 'create', 'update', 'delete'
            contract_id: Required for update, delete
            contract_type_id: Contract type ID (create - REQUIRED).
                1=Lease, 2=Maintenance, 3=Software License, 4=Warranty.
            name: Contract name (create - REQUIRED)
            description: Contract description
            vendor_id: Vendor ID (create - REQUIRED)
            approver_id: Approver ID (create - REQUIRED)
            start_date: ISO date YYYY-MM-DD (create - REQUIRED)
            end_date: ISO date YYYY-MM-DD (create - REQUIRED)
            cost: Total contract cost (create - REQUIRED)
            contract_number: Unique contract number (create - REQUIRED)
            auto_renew: Auto-renew flag (bool)
            notify_expiry: Notify on expiry (bool)
            notify_before: Days before expiry to notify (int)
            visible_to_id: Visibility scope ID
            software_id: Associated software ID
            notify_to: List of email addresses to notify
            billing_cycle: One of 'monthly', 'quarterly', 'half_yearly', 'annual', 'one_time'
            associated_asset_ids: List of asset IDs to associate
            item_cost_details: List of item cost detail dicts
            custom_fields: Custom fields dict
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_CONTRACT, "manage_contract", "read_contract")
        if err:
            return err
        return await _contract_handler(
            action, contract_id, contract_type_id, name, description, vendor_id,
            approver_id, start_date, end_date, cost, contract_number, auto_renew,
            notify_expiry, notify_before, visible_to_id, software_id, notify_to,
            billing_cycle, associated_asset_ids, item_cost_details, custom_fields,
            page=1, per_page=30,
        )
