# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class WorkOrder(Document):

    def validate(self):
        self.route_approval()
        self.set_completion_timestamp()

    def route_approval(self):
        """Compute whether this work order needs owner approval, based on
        the Property's Maintenance Approval Limit (or the fuller
        Management Agreement's limit, once Phase 6 introduces it). Kept as
        a plain field (rather than a live DB check inside the Workflow's
        transition condition) so the Workflow condition can stay a simple,
        safe `doc.approval_required == ...` expression."""
        limit = None
        if self.property:
            limit = frappe.db.get_value("Property", self.property, "maintenance_approval_limit")
        self.approval_required = 1 if (limit and flt(self.estimated_cost) > flt(limit)) else 0

    def set_completion_timestamp(self):
        if self.status in ("Completed", "Closed") and not self.completed_on:
            self.completed_on = now_datetime()
        elif self.status not in ("Completed", "Closed"):
            self.completed_on = None

    def on_update(self):
        self.maybe_create_vendor_bill()

    def maybe_create_vendor_bill(self):
        if (
            self.status == "Completed"
            and self.vendor
            and flt(self.actual_cost) > 0
            and not self.purchase_invoice
        ):
            from pms.pms.billing import create_vendor_bill
            create_vendor_bill(self)
