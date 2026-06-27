"""Freshservice MCP — Procurement tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_purchase_order / manage_purchase_order — list/get vs create/update
  - read_vendor         / manage_vendor         — list/get vs create/update/delete
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
from ._split import normalize_action, reject_unless_in


def register_procurement_tools(mcp) -> None:
    """Register procurement-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  purchase_order — read/manage split                                 #
    # ------------------------------------------------------------------ #
    _READ_PO = {"list", "get"}
    _WRITE_PO = {"create", "update"}

    async def _purchase_order_handler(
        action: str,
        purchase_order_id: Optional[int],
        vendor_id: Optional[int],
        name: Optional[str],
        po_number: Optional[str],
        vendor_details: Optional[str],
        expected_delivery_date: Optional[str],
        shipping_address: Optional[str],
        billing_address: Optional[str],
        billing_same_as_shipping: Optional[bool],
        currency_code: Optional[str],
        conversion_rate: Optional[float],
        department_id: Optional[int],
        discount_percentage: Optional[float],
        tax_percentage: Optional[float],
        shipping_cost: Optional[float],
        purchase_items: Optional[List[Dict[str, Any]]],
        custom_fields: Optional[Dict[str, Any]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        # ---------- list ----------
        if action == "list":
            try:
                resp = await api_get(
                    "purchase_orders", params={"page": page, "per_page": per_page}
                )
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "purchase_orders": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list purchase orders")

        # ---------- get ----------
        if action == "get":
            if not purchase_order_id:
                return {"error": "purchase_order_id required for get"}
            try:
                resp = await api_get(f"purchase_orders/{purchase_order_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get purchase order")

        # ---------- create ----------
        if action == "create":
            if not vendor_id:
                return {"error": "vendor_id is required for create"}
            data: Dict[str, Any] = {"vendor_id": vendor_id}
            for k, v in [
                ("name", name),
                ("po_number", po_number),
                ("vendor_details", vendor_details),
                ("expected_delivery_date", expected_delivery_date),
                ("shipping_address", shipping_address),
                ("billing_address", billing_address),
                ("billing_same_as_shipping", billing_same_as_shipping),
                ("currency_code", currency_code),
                ("conversion_rate", conversion_rate),
                ("department_id", department_id),
                ("discount_percentage", discount_percentage),
                ("tax_percentage", tax_percentage),
                ("shipping_cost", shipping_cost),
                ("purchase_items", purchase_items),
                ("custom_fields", custom_fields),
            ]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("purchase_orders", json=data)
                resp.raise_for_status()
                return {"success": True, "purchase_order": resp.json()}
            except Exception as e:
                return handle_error(e, "create purchase order")

        # ---------- update ----------
        if action == "update":
            if not purchase_order_id:
                return {"error": "purchase_order_id required for update"}
            data = {}
            for k, v in [
                ("vendor_id", vendor_id),
                ("name", name),
                ("po_number", po_number),
                ("vendor_details", vendor_details),
                ("expected_delivery_date", expected_delivery_date),
                ("shipping_address", shipping_address),
                ("billing_address", billing_address),
                ("currency_code", currency_code),
                ("conversion_rate", conversion_rate),
                ("department_id", department_id),
                ("discount_percentage", discount_percentage),
                ("tax_percentage", tax_percentage),
                ("shipping_cost", shipping_cost),
                ("purchase_items", purchase_items),
                ("custom_fields", custom_fields),
            ]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(
                    f"purchase_orders/{purchase_order_id}", json=data
                )
                resp.raise_for_status()
                return {"success": True, "purchase_order": resp.json()}
            except Exception as e:
                return handle_error(e, "update purchase order")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_purchase_order(
        action: str,
        purchase_order_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice purchase orders.

        Actions: list, get

        Required per action:
          get: purchase_order_id

        Optional: page, per_page (list).
        """
        action = normalize_action(action, _READ_PO)
        err = reject_unless_in(action, _READ_PO, "read_purchase_order", "manage_purchase_order")
        if err:
            return err
        return await _purchase_order_handler(
            action, purchase_order_id, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, page, per_page,
        )

    @mcp.tool()
    async def manage_purchase_order(
        action: str,
        purchase_order_id: Optional[int] = None,
        vendor_id: Optional[int] = None,
        name: Optional[str] = None,
        po_number: Optional[str] = None,
        vendor_details: Optional[str] = None,
        expected_delivery_date: Optional[str] = None,
        shipping_address: Optional[str] = None,
        billing_address: Optional[str] = None,
        billing_same_as_shipping: Optional[bool] = None,
        currency_code: Optional[str] = None,
        conversion_rate: Optional[float] = None,
        department_id: Optional[int] = None,
        discount_percentage: Optional[float] = None,
        tax_percentage: Optional[float] = None,
        shipping_cost: Optional[float] = None,
        purchase_items: Optional[List[Dict[str, Any]]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice purchase orders.

        Actions: create, update

        Required per action:
          create: vendor_id
          update: purchase_order_id

        Optional fields:
          name, po_number, vendor_details, expected_delivery_date (YYYY-MM-DD),
          shipping_address, billing_address, billing_same_as_shipping,
          currency_code, conversion_rate, department_id, discount_percentage,
          tax_percentage, shipping_cost, custom_fields
          purchase_items: list of dicts (item_type, item_name, cost, quantity,
            tax_percentage required; description, item_id optional)

        Tax: per-item tax (in purchase_items) and per-order tax_percentage
        are independent — setting both will double-tax.
        """
        action = normalize_action(action, _WRITE_PO)
        err = reject_unless_in(action, _WRITE_PO, "manage_purchase_order", "read_purchase_order")
        if err:
            return err
        return await _purchase_order_handler(
            action, purchase_order_id, vendor_id, name, po_number, vendor_details,
            expected_delivery_date, shipping_address, billing_address,
            billing_same_as_shipping, currency_code, conversion_rate, department_id,
            discount_percentage, tax_percentage, shipping_cost, purchase_items,
            custom_fields, page=1, per_page=30,
        )

    # ------------------------------------------------------------------ #
    #  vendor — read/manage split                                         #
    # ------------------------------------------------------------------ #
    _READ_VENDOR = {"list", "get"}
    _WRITE_VENDOR = {"create", "update", "delete"}

    async def _vendor_handler(
        action: str,
        vendor_id: Optional[int],
        name: Optional[str],
        description: Optional[str],
        primary_email: Optional[str],
        address: Optional[str],
        contact_name: Optional[str],
        phone: Optional[str],
        custom_fields: Optional[Dict[str, Any]],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        # ---------- list ----------
        if action == "list":
            try:
                resp = await api_get(
                    "vendors", params={"page": page, "per_page": per_page}
                )
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "vendors": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                        "per_page": per_page,
                    },
                }
            except Exception as e:
                return handle_error(e, "list vendors")

        # ---------- get ----------
        if action == "get":
            if not vendor_id:
                return {"error": "vendor_id required for get"}
            try:
                resp = await api_get(f"vendors/{vendor_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get vendor")

        # ---------- create ----------
        if action == "create":
            if not name:
                return {"error": "name is required for create"}
            data: Dict[str, Any] = {"name": name}
            for k, v in [
                ("description", description),
                ("primary_email", primary_email),
                ("address", address),
                ("contact_name", contact_name),
                ("phone", phone),
                ("custom_fields", custom_fields),
            ]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("vendors", json=data)
                resp.raise_for_status()
                return {"success": True, "vendor": resp.json()}
            except Exception as e:
                return handle_error(e, "create vendor")

        # ---------- update ----------
        if action == "update":
            if not vendor_id:
                return {"error": "vendor_id required for update"}
            data = {}
            for k, v in [
                ("name", name),
                ("description", description),
                ("primary_email", primary_email),
                ("address", address),
                ("contact_name", contact_name),
                ("phone", phone),
                ("custom_fields", custom_fields),
            ]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"vendors/{vendor_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "vendor": resp.json()}
            except Exception as e:
                return handle_error(e, "update vendor")

        # ---------- delete ----------
        if action == "delete":
            if not vendor_id:
                return {"error": "vendor_id required for delete"}
            try:
                resp = await api_delete(f"vendors/{vendor_id}")
                if resp.status_code == 204:
                    return {"success": True, "message": "Vendor deleted"}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "delete vendor")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_vendor(
        action: str,
        vendor_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice vendors.

        Actions: list, get

        Required per action:
          get: vendor_id

        Optional: page, per_page (list).
        """
        action = normalize_action(action, _READ_VENDOR)
        err = reject_unless_in(action, _READ_VENDOR, "read_vendor", "manage_vendor")
        if err:
            return err
        return await _vendor_handler(
            action, vendor_id, None, None, None, None, None, None, None,
            page, per_page,
        )

    @mcp.tool()
    async def manage_vendor(
        action: str,
        vendor_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        primary_email: Optional[str] = None,
        address: Optional[str] = None,
        contact_name: Optional[str] = None,
        phone: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice vendors.

        Actions: create, update, delete

        Required per action:
          create: name
          update / delete: vendor_id

        Optional: description, primary_email, address, contact_name, phone,
        custom_fields.
        """
        action = normalize_action(action, _WRITE_VENDOR)
        err = reject_unless_in(action, _WRITE_VENDOR, "manage_vendor", "read_vendor")
        if err:
            return err
        return await _vendor_handler(
            action, vendor_id, name, description, primary_email, address,
            contact_name, phone, custom_fields, page=1, per_page=30,
        )
