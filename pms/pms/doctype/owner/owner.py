# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address


class Owner(Document):

    def validate(self):
        if self.email:
            validate_email_address(self.email.strip(), throw=True)

    def after_insert(self):
        self.create_supplier()

    def on_update(self):
        if not self.supplier:
            self.create_supplier()
        else:
            self.sync_supplier()

    def on_trash(self):
        """Block deletion if this owner still holds a share of any Property."""
        linked_property = frappe.db.exists("Property Owner", {"owner": self.name})
        if linked_property:
            frappe.throw(
                f"Cannot delete Owner <b>{self.owner_name}</b>: still linked to a Property. "
                f"Remove the ownership row first."
            )

    # ------------------------------------------------------------
    # Supplier sync (mirrors Tenant.create_customer / sync_customer)
    # ------------------------------------------------------------
    def _get_supplier_group(self):
        group = frappe.db.get_single_value("Buying Settings", "supplier_group")
        if group and not frappe.db.get_value("Supplier Group", group, "is_group"):
            return group
        if frappe.db.exists("Supplier Group", "Owner"):
            return "Owner"
        group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
        return group or "All Supplier Groups"

    def create_supplier(self):
        """Create (or reuse) a Supplier so this owner can receive
        management-fee-netted distributions via Payment Entry."""
        existing = frappe.db.exists("Supplier", {"supplier_name": self.owner_name})
        if existing:
            self.db_set("supplier", existing)
            return

        supplier = frappe.get_doc({
            "doctype"       : "Supplier",
            "supplier_name" : self.owner_name,
            "supplier_type" : self.owner_type or "Individual",
            "supplier_group": self._get_supplier_group(),
            "mobile_no"     : self.mobile_no,
            "email_id"      : self.email,
        })
        supplier.insert(ignore_permissions=True)
        self.db_set("supplier", supplier.name)

        frappe.msgprint(
            f"✅ Supplier <b>{supplier.name}</b> created and linked.",
            indicator="green",
            alert=True,
        )

    def sync_supplier(self):
        if not frappe.db.exists("Supplier", self.supplier):
            return
        frappe.db.set_value(
            "Supplier",
            self.supplier,
            {
                "mobile_no": self.mobile_no,
                "email_id" : self.email,
            },
        )
