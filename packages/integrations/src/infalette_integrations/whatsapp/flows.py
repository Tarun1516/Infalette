"""WhatsApp Flow management."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

from infalette_integrations.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

# Keys under which flow submissions commonly nest selected line items
_ITEM_LIST_KEYS = ("items", "products", "cart", "selections", "order", "line_items", "lines")
_PRODUCT_KEYS = ("product_id", "productId", "id")
_SKU_KEYS = ("sku", "SKU", "product_sku")
_QTY_KEYS = ("quantity", "qty", "count")

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class WhatsAppFlowManager:
    """Manages WhatsApp Flows for product selection and address collection."""

    def __init__(self) -> None:
        self._client = WhatsAppClient()

    async def create_product_selection_flow(
        self,
        flow_name: str,
        products: list[dict],
    ) -> dict:
        """Create a product selection flow."""
        flow_data = {
            "screen": {
                "type": "product_selection",
                "title": "Select Products",
                "products": products,
            }
        }
        return await self._client.create_flow(flow_name, flow_data)

    async def create_address_collection_flow(
        self,
        flow_name: str,
        fields: list[str] = None,
    ) -> dict:
        """Create an address collection flow."""
        if fields is None:
            fields = ["name", "address", "city", "state", "pincode", "phone"]

        flow_data = {
            "screen": {
                "type": "form",
                "title": "Shipping Address",
                "fields": [{"name": f, "type": "text", "required": True} for f in fields],
            }
        }
        return await self._client.create_flow(flow_name, flow_data)

    async def get_flow_responses(
        self,
        flow_id: str,
    ) -> dict:
        """Get responses for a flow."""
        return await self._client.get_flow(flow_id)

    async def handle_flow_error(
        self,
        flow_id: str,
        error: Exception,
    ) -> None:
        """Handle a flow error."""
        logger.error(f"WhatsApp Flow error: flow_id={flow_id}, error={error}", exc_info=True)

    def flow_template_builder(
        self,
        flow_type: str,
        title: str,
        fields: list[dict],
    ) -> dict:
        """Build a flow template."""
        return {
            "screen": {
                "type": flow_type,
                "title": title,
                "fields": fields,
            }
        }


def parse_flow_selections(message: dict) -> Optional[list[dict]]:
    """Parse product selections from an inbound WhatsApp message, tolerantly.

    Recognises:
    - ``interactive.nfm_reply.response_json`` (WhatsApp Flow submission; JSON
      string or already-decoded dict)
    - ``interactive.button_reply`` / ``interactive.list_reply`` ids containing
      product ids or SKUs
    - legacy ``button.id`` replies

    Returns a list of ``{"product_id"|"sku", "quantity"}`` dicts (possibly
    empty when a flow submitted no resolvable selections), or ``None`` when
    the message is not a flow/order submission at all.
    """
    if not isinstance(message, dict):
        return None

    interactive = message.get("interactive") or {}

    # --- nfm_reply (WhatsApp Flows) ---
    nfm = interactive.get("nfm_reply") or {}
    response_json = nfm.get("response_json")
    if response_json is not None:
        data = _coerce_flow_data(response_json)
        items = _extract_items(data)
        return items

    # --- button / list replies carrying product references ---
    reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
    token = reply.get("id") or ""
    if not token:
        legacy_button = message.get("button") or {}
        token = legacy_button.get("id") or ""

    if token:
        selection = _selection_from_token(token)
        if selection is not None:
            return [selection]

    return None


def _coerce_flow_data(response_json: Any) -> dict:
    """Decode response_json whether it arrives as a JSON string or dict."""
    if isinstance(response_json, str):
        try:
            decoded = json.loads(response_json)
        except (TypeError, ValueError):
            logger.warning("Could not parse flow response_json as JSON")
            return {}
        return decoded if isinstance(decoded, dict) else {"items": decoded}
    if isinstance(response_json, dict):
        return response_json
    return {}


def _extract_items(data: dict) -> list[dict]:
    """Scan flow payload for line-item-like structures."""
    candidates: list[Any] = []
    for key in _ITEM_LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            candidates.append(value)
    if not candidates:
        # Tolerate flat single-item payloads like {"sku": "X", "quantity": 2}
        single = _selection_from_dict(data)
        return [single] if single else []
    # Prefer the first list whose entries look like product selections
    for value in candidates:
        items = [_s for _s in (_selection_from_dict(entry) for entry in value) if _s]
        if items:
            return items
    # Also tolerate nested dicts under list keys e.g. {"cart": {...}}
    for value in data.values():
        if isinstance(value, dict):
            nested = value.get("items") or value.get("products")
            if isinstance(nested, list):
                items = [_s for _s in (_selection_from_dict(e) for e in nested) if _s]
                if items:
                    return items
    return []


def _selection_from_dict(entry: Any) -> Optional[dict]:
    """Normalize one entry into {product_id|sku, quantity}."""
    if isinstance(entry, str):
        return _selection_from_token(entry)
    if not isinstance(entry, dict):
        return None

    product_id = next((entry[k] for k in _PRODUCT_KEYS if entry.get(k)), None)
    sku = next((entry[k] for k in _SKU_KEYS if entry.get(k)), None)
    qty_raw = next((entry[k] for k in _QTY_KEYS if entry.get(k) is not None), 1)
    try:
        quantity = max(1, int(qty_raw))
    except (TypeError, ValueError):
        quantity = 1

    if product_id and _looks_like_uuid(str(product_id)):
        return {"product_id": str(product_id), "quantity": quantity}
    if sku:
        return {"sku": str(sku), "quantity": quantity}
    if product_id:
        # Non-UUID id — treat as SKU reference so tenant resolution can still try
        return {"sku": str(product_id), "quantity": quantity}
    return None


def _selection_from_token(token: str) -> Optional[dict]:
    """Parse a reply id like 'add_to_cart:SKU123:2', 'SKU123' or a UUID."""
    parts = [p for p in re.split(r"[:|]", str(token).strip()) if p]
    if not parts:
        return None

    quantity = 1
    refs: list[str] = []
    for part in parts:
        if part.isdigit() and int(part) > 0 and len(parts) > 1:
            quantity = int(part)
        elif part.lower() in ("add_to_cart", "buy", "order", "product", "item"):
            continue
        else:
            refs.append(part)

    if not refs:
        return None
    ref = refs[-1]
    if _looks_like_uuid(ref):
        return {"product_id": ref, "quantity": quantity}
    return {"sku": ref, "quantity": quantity}


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
