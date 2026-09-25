# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, add_to_date
from pms.pms.doctype.unit.unit import sync_unit_listing

SLA_HOURS = {"Urgent": 4, "High": 24, "Medium": 72, "Low": 168}


class WorkOrder(Document):

    def validate(self):
        self.route_approval()
        self.set_completion_timestamp()
        self.set_sla_due_by()

    def route_approval(self):
        """Compute whether this work order needs owner approval. A
        Management Agreement's own approval_limit (Phase 6) takes
        priority over the Property's simpler fallback field (Phase 4),
        since the agreement is the authoritative, owner-specific source
        once one exists. Kept as a plain field (rather than a live DB
        check inside the Workflow's transition condition) so the
        Workflow condition can stay a simple, safe
        `doc.approval_required == ...` expression."""
        limit = None
        if self.property:
            limit = frappe.db.get_value(
                "Management Agreement", {"property": self.property}, "approval_limit"
            )
            if not limit:
                limit = frappe.db.get_value("Property", self.property, "maintenance_approval_limit")
        self.approval_required = 1 if (limit and flt(self.estimated_cost) > flt(limit)) else 0

    def set_completion_timestamp(self):
        if self.status in ("Completed", "Closed") and not self.completed_on:
            self.completed_on = now_datetime()
        elif self.status not in ("Completed", "Closed"):
            self.completed_on = None

    def set_sla_due_by(self):
        if not self.sla_due_by and self.status == "Open":
            hours = SLA_HOURS.get(self.priority, SLA_HOURS["Medium"])
            self.sla_due_by = add_to_date(now_datetime(), hours=hours)
        if self.status in ("Completed", "Closed"):
            self.sla_breached = 0 if not self.sla_breached else self.sla_breached

    def on_update(self):
        self.maybe_create_vendor_bill()
        self.maybe_recharge_tenant()
        self.maybe_release_make_ready_unit()

    def maybe_create_vendor_bill(self):
        if (
            self.status == "Completed"
            and self.bill_to == "Owner"
            and self.vendor
            and flt(self.actual_cost) > 0
            and not self.purchase_invoice
        ):
            from pms.pms.billing import create_vendor_bill
            create_vendor_bill(self)

    def maybe_recharge_tenant(self):
        """When the tenant caused the damage, bill them directly (Sales
        Invoice) instead of charging the owner."""
        if (
            self.status == "Completed"
            and self.bill_to == "Tenant"
            and flt(self.actual_cost) > 0
            and not self.sales_invoice
            and self.unit
        ):
            from pms.pms.billing import create_tenant_recharge_invoice
            create_tenant_recharge_invoice(self)

    def maybe_release_make_ready_unit(self):
        """A make-ready job (created automatically on Move Out) closing
        means the unit is finally ready to hand to the next tenant."""
        if self.is_make_ready and self.status == "Closed" and self.unit:
            current = frappe.db.get_value("Unit", self.unit, "status")
            if current == "Under Maintenance":
                frappe.db.set_value("Unit", self.unit, "status", "Vacant")
                sync_unit_listing(self.unit, "Vacant")

    @frappe.whitelist()
    def confirm_by_tenant(self):
        """Called from the tenant portal: confirm the fix is done. Only
        the tenant who filed the linked Maintenance Request may confirm."""
        if not self.maintenance_request:
            frappe.throw("This work order has no linked Maintenance Request to confirm against.")

        tenant = frappe.db.get_value("Maintenance Request", self.maintenance_request, "tenant")
        tenant_email = frappe.db.get_value("Tenant", tenant, "email") if tenant else None
        if not tenant_email or tenant_email != frappe.session.user:
            frappe.throw("You can only confirm work orders raised from your own requests.", frappe.PermissionError)

        self.db_set("tenant_confirmed", 1)
        return True
