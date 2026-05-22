"""Freshservice MCP — Products tools (consolidated).

Each tool is exposed as a read_/manage_ pair so MCP clients can grant
read-only or read-write access independently.

Tools:
  - read_product / manage_product — list/get vs create/update
"""
from typing import Any, Dict, Optional, Union

from ..http_client import api_get, api_post, api_put, handle_error, parse_link_header
from ._split import reject_unless_in


def register_products_tools(mcp) -> None:
    """Register product-related tools on *mcp*."""

    # ------------------------------------------------------------------ #
    #  product — read/manage split                                        #
    # ------------------------------------------------------------------ #
    _READ_PRODUCT = {"list", "get"}
    _WRITE_PRODUCT = {"create", "update"}

    async def _product_handler(
        action: str,
        product_id: Optional[int],
        name: Optional[str],
        asset_type_id: Optional[int],
        manufacturer: Optional[str],
        status: Optional[Union[str, int]],
        mode_of_procurement: Optional[str],
        depreciation_type_id: Optional[int],
        description: Optional[str],
        description_text: Optional[str],
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        if action == "list":
            try:
                resp = await api_get("products", params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                pagination_info = parse_link_header(resp.headers.get("Link", ""))
                return {
                    "products": resp.json(),
                    "pagination": {
                        "current_page": page,
                        "next_page": pagination_info.get("next"),
                        "prev_page": pagination_info.get("prev"),
                    },
                }
            except Exception as e:
                return handle_error(e, "list products")

        if action == "get":
            if not product_id:
                return {"error": "product_id required for get"}
            try:
                resp = await api_get(f"products/{product_id}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return handle_error(e, "get product")

        if action == "create":
            if not name or not asset_type_id:
                return {"error": "name and asset_type_id required for create"}
            data: Dict[str, Any] = {"name": name, "asset_type_id": asset_type_id}
            for k, v in [("manufacturer", manufacturer), ("status", status),
                         ("mode_of_procurement", mode_of_procurement),
                         ("depreciation_type_id", depreciation_type_id),
                         ("description", description),
                         ("description_text", description_text)]:
                if v is not None:
                    data[k] = v
            try:
                resp = await api_post("products", json=data)
                resp.raise_for_status()
                return {"success": True, "product": resp.json()}
            except Exception as e:
                return handle_error(e, "create product")

        if action == "update":
            if not product_id:
                return {"error": "product_id required for update"}
            data: Dict[str, Any] = {}
            for k, v in [("name", name), ("asset_type_id", asset_type_id),
                         ("manufacturer", manufacturer), ("status", status),
                         ("mode_of_procurement", mode_of_procurement),
                         ("depreciation_type_id", depreciation_type_id),
                         ("description", description),
                         ("description_text", description_text)]:
                if v is not None:
                    data[k] = v
            if not data:
                return {"error": "No fields provided for update"}
            try:
                resp = await api_put(f"products/{product_id}", json=data)
                resp.raise_for_status()
                return {"success": True, "product": resp.json()}
            except Exception as e:
                return handle_error(e, "update product")

        return {"error": "unreachable"}

    @mcp.tool()
    async def read_product(
        action: str,
        product_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> Dict[str, Any]:
        """Read Freshservice products.

        Args:
            action: 'list', 'get'
            product_id: Required for get
            page: Page number (list)
            per_page: Items per page (list)
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _READ_PRODUCT, "read_product", "manage_product")
        if err:
            return err
        return await _product_handler(
            action, product_id, None, None, None, None, None, None, None, None,
            page, per_page,
        )

    @mcp.tool()
    async def manage_product(
        action: str,
        product_id: Optional[int] = None,
        name: Optional[str] = None,
        asset_type_id: Optional[int] = None,
        manufacturer: Optional[str] = None,
        status: Optional[Union[str, int]] = None,
        mode_of_procurement: Optional[str] = None,
        depreciation_type_id: Optional[int] = None,
        description: Optional[str] = None,
        description_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write actions on Freshservice products.

        Args:
            action: 'create', 'update'
            product_id: Required for update
            name: Product name (create — MANDATORY)
            asset_type_id: Asset type ID (create — MANDATORY)
            manufacturer: Manufacturer name
            status: Product status (str or int)
            mode_of_procurement: e.g. 'buy', 'lease'
            depreciation_type_id: Depreciation type ID
            description: HTML description
            description_text: Plain text description
        """
        action = action.lower().strip()
        err = reject_unless_in(action, _WRITE_PRODUCT, "manage_product", "read_product")
        if err:
            return err
        return await _product_handler(
            action, product_id, name, asset_type_id, manufacturer, status,
            mode_of_procurement, depreciation_type_id, description, description_text,
            page=1, per_page=30,
        )
