# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class ChargeType(Document):

    def validate(self):
        if not self.item:
            self.item = self.ensure_item()

    def ensure_item(self):
        """Lazily create a non-stock service Item for this charge type,
        generalizing the ad-hoc item creation that billing.ensure_item()
        does for individual invoice lines."""
        item_code = f"Charge-{self.charge_name}"
        if frappe.db.exists("Item", item_code):
            return item_code

        item = frappe.get_doc({
            "doctype"      : "Item",
            "item_code"    : item_code,
            "item_name"    : self.charge_name,
            "item_group"   : "Services",
            "is_stock_item": 0,
            "stock_uom"    : "Nos",
        })
        item.insert(ignore_permissions=True)
        return item.name
