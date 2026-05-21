"""Freshservice MCP — Procurement tools (consolidated).

Exposes 2 tools:
  • manage_purchase_order — CRUD + list
  • manage_vendor         — CRUD + list + delete
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


def register_procurement_tools(mcp) -> None:
    """Register procurement-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  manage_purchase_order                                               #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_purchase_order(
        action: str,
        purchase_order_id: Optional[int] = None,
        # create / update fields
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
        # list
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Unified purchase order operations.

        Args:
            action: One of 'create', 'update', 'get', 'list'
            purchase_order_id: PO ID (get, update)
            vendor_id: Vendor ID (create — MANDATORY)
            name: Title of the purchase order
            po_number: Unique purchase order number
            vendor_details: Details of the vendor
            expected_delivery_date: Expected delivery date (YYYY-MM-DD)
            shipping_address: Shipping address
            billing_address: Billing address
            billing_same_as_shipping: Whether billing matches shipping
            currency_code: Currency code (e.g. 'USD')
            conversion_rate: Currency conversion rate
            department_id: Department ID
            discount_percentage: Discount percentage on the order
            tax_percentage: Order-level tax percentage
            shipping_cost: Shipping cost
            purchase_items: List of item dicts, each with item_type, item_name,
                cost, quantity, tax_percentage (all required), plus optional
                description and item_id
            custom_fields: Custom field key-value pairs
            page: Page number (list)
            per_page: Items per page (list)

        Tax Notes:
            There are TWO tax levels: per-item (in purchase_items) and per-order
            (tax_percentage). Do not set both to avoid double taxation.
        """
        action = action.lower().strip()

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
            data: Dict[str, Any] = {}
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

        return {
            "error": f"Unknown action '{action}'. Valid: create, update, get, list"
        }

    # ------------------------------------------------------------------ #
    #  manage_vendor                                                       #
    # ------------------------------------------------------------------ #
    @mcp.tool()
    async def manage_vendor(
        action: str,
        vendor_id: Optional[int] = None,
        # create / update fields
        name: Optional[str] = None,
        description: Optional[str] = None,
        primary_email: Optional[str] = None,
        address: Optional[str] = None,
        contact_name: Optional[str] = None,
        phone: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        # list
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Unified vendor operations.

        Vendors are suppliers or service providers referenced in purchase orders
        and associated with assets.

        Args:
            action: One of 'create', 'update', 'get', 'list', 'delete'
            vendor_id: Vendor ID (get, update, delete)
            name: Vendor name (create — MANDATORY)
            description: Vendor description
            primary_email: Primary contact email
            address: Physical address
            contact_name: Primary contact person name
            phone: Contact phone number
            custom_fields: Custom field key-value pairs
            page: Page number (list)
            per_page: Items per page (list)
        """
        action = action.lower().strip()

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
            data: Dict[str, Any] = {}
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

        return {
            "error": f"Unknown action '{action}'. Valid: create, update, get, list, delete"
        }
