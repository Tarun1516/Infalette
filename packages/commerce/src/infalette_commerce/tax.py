"""Tax calculation service.

GST model (India):
- Rate comes from the product tax_class slab; a tenant may override the
  default slab mapping via ``Store.tax_rate``/tax profile passed as
  ``store_override``.
- Intra-state supply (supplier state == ship-to state) splits into
  CGST + SGST; inter-state supply is IGST.
"""

from __future__ import annotations

from typing import Optional

# Union Territories with a unified GST (UTGST only) — treated like
# union territories for the CGST split.
UNION_TERRITORIES = {
    "andaman and nicobar islands",
    "chandigarh",
    "dadra and nagar haveli and daman and diu",
    "delhi",
    "jammu and kashmir",
    "ladakh",
    "lakshadweep",
    "puducherry",
}


class TaxService:
    """Tax calculation for orders."""

    TAX_RATES = {
        "standard": 0.18,  # 18% GST for India
        "reduced": 0.05,   # 5% GST
        "zero": 0.0,       # 0% GST
        "exempt": 0.0,     # Exempt
    }

    def calculate_tax(
        self,
        amount_cents: int,
        tax_class: str,
        address: Optional[dict] = None,
        store_override: Optional[int] = None,
        supplier_state: Optional[str] = None,
    ) -> int:
        """Calculate tax amount for a given amount and tax class.

        GST slabs are product-class driven (standard/reduced/zero/exempt),
        not state driven. ``store_override`` is the tenant's flat percentage
        (e.g. 12) applied when the product carries no specific tax_class.
        """
        if not tax_class and store_override is not None:
            rate = max(0.0, float(store_override)) / 100.0
            return int(amount_cents * rate)

        rate = self.TAX_RATES.get(tax_class, self.TAX_RATES["standard"])
        return int(amount_cents * rate)

    def get_tax_rate(
        self,
        tax_class: str,
        region: Optional[str] = None,
    ) -> float:
        """Get the tax rate for a tax class."""
        return self.TAX_RATES.get(tax_class, self.TAX_RATES["standard"])

    @staticmethod
    def gst_breakdown(
        amount_cents: int,
        rate: float,
        supplier_state: str,
        shipping_state: str,
    ) -> dict:
        """Split GST into IGST or CGST+SGST components.

        Returns {"mode": "inter_state"|"intra_state", "igst_cents": int} or
        {"mode": ..., "cgst_cents": int, "sgst_cents"/"utgst_cents": int}.
        """
        total_tax = int(amount_cents * rate)
        supplier = (supplier_state or "").strip().lower()
        destination = (shipping_state or "").strip().lower()

        intra = bool(supplier) and supplier == destination
        half = total_tax // 2
        remainder = total_tax - (half * 2)
        utgst = destination in UNION_TERRITORIES

        if intra:
            return {
                "mode": "intra_state",
                "cgst_cents": half + remainder,
                ("utgst_cents" if utgst else "sgst_cents"): half,
                "total_tax_cents": total_tax,
                "rate": rate,
            }
        return {
            "mode": "inter_state",
            "igst_cents": total_tax,
            "total_tax_cents": total_tax,
            "rate": rate,
        }

    def apply_tax_to_order(
        self,
        items: list[dict],
        shipping_address: dict,
        supplier_state: Optional[str] = None,
    ) -> dict:
        """Apply tax to all items in an order."""
        total_tax = 0
        item_taxes = []

        for item in items:
            taxable = item.get("price_cents", 0) * item.get("quantity", 0)
            rate = self.get_tax_rate(item.get("tax_class", "standard"))
            breakdown = self.gst_breakdown(
                taxable,
                rate,
                supplier_state or "",
                shipping_address.get("state", ""),
            )
            tax_amount = breakdown["total_tax_cents"]
            total_tax += tax_amount
            item_taxes.append({
                "product_id": item.get("product_id"),
                "tax_amount": tax_amount,
                "gst_mode": breakdown["mode"],
            })

        return {
            "total_tax_cents": total_tax,
            "item_taxes": item_taxes,
        }

    def handle_tax_exempt_customers(
        self,
        customer,
        amount_cents: int,
    ) -> int:
        """Handle tax exemption for eligible customers."""
        if customer and getattr(customer, "tax_exempt", False):
            return 0
        return self.calculate_tax(amount_cents, "standard")
