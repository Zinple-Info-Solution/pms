# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address


class Tenant(Document):

    def validate(self):
        self.validate_email()
        self.validate_duplicate_mobile()

    def after_insert(self):
        self.create_customer()

    def on_update(self):
        if not self.customer:
            self.create_customer()
        else:
            self.sync_customer()

    def on_trash(self):
        """Block deletion if tenant has any non-cancelled Lease Agreement."""
        active_lease = frappe.db.exists(
            "Lease Agreement",
            {"tenant": self.name, "docstatus": ["<", 2]},
        )
        if active_lease:
            frappe.throw(
                f"Cannot delete Tenant <b>{self.full_name}</b>: "
                f"Lease Agreement <b>{active_lease}</b> exists for this tenant. "
                f"Cancel the lease first."
            )

    # ------------------------------------------------------------
    # Validations
    # ------------------------------------------------------------
    def validate_email(self):
        if self.email:
            validate_email_address(self.email.strip(), throw=True)

    def validate_duplicate_mobile(self):
        if not self.mobile_no:
            return
        duplicate = frappe.db.exists(
            "Tenant",
            {"mobile_no": self.mobile_no, "name": ["!=", self.name]},
        )
        if duplicate:
            frappe.throw(
                f"Mobile No <b>{self.mobile_no}</b> is already used by "
                f"Tenant <b>{duplicate}</b>."
            )

    # ------------------------------------------------------------
    # Customer sync
    # ------------------------------------------------------------
    def _get_customer_group(self):
        """Get a valid non-group Customer Group"""
        # First try Selling Settings default
        group = frappe.db.get_single_value("Selling Settings", "customer_group")
        if group and not frappe.db.get_value("Customer Group", group, "is_group"):
            return group

        # Try 'Tenant' group specifically
        if frappe.db.exists("Customer Group", "Tenant"):
            return "Tenant"

        # Fallback — first non-group customer group
        group = frappe.db.get_value(
            "Customer Group",
            {"is_group": 0},
            "name"
        )
        return group or "Commercial"

    def _get_territory(self):
        """Get a valid non-group Territory"""
        territory = frappe.db.get_single_value("Selling Settings", "territory")
        if territory and not frappe.db.get_value("Territory", territory, "is_group"):
            return territory

        # Fallback — first non-group territory
        territory = frappe.db.get_value(
            "Territory",
            {"is_group": 0},
            "name"
        )
        return territory or "Rest Of The World"

    def create_customer(self):
        """Create (or reuse) a Customer so this tenant can be used
        in Lease Agreements and Sales Invoices."""
        existing = frappe.db.exists("Customer", {"customer_name": self.full_name})
        if existing:
            self.db_set("customer", existing)
            return

        customer = frappe.get_doc({
            "doctype"        : "Customer",
            "customer_name"  : self.full_name,
            "customer_type"  : self.tenant_type or "Individual",
            "customer_group" : self._get_customer_group(),  # ✅ safe
            "territory"      : self._get_territory(),       # ✅ safe
            "mobile_no"      : self.mobile_no,
            "email_id"       : self.email,
        })
        customer.insert(ignore_permissions=True)
        self.db_set("customer", customer.name)

        frappe.msgprint(
            f"✅ Customer <b>{customer.name}</b> created and linked.",
            indicator="green",
            alert=True,
        )

    def sync_customer(self):
        """Keep basic contact info in sync with the linked Customer."""
        if not frappe.db.exists("Customer", self.customer):
            return
        frappe.db.set_value(
            "Customer",
            self.customer,
            {
                "mobile_no": self.mobile_no,
                "email_id" : self.email,
            },
        )