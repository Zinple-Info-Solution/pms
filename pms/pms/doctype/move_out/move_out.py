# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from pms.pms.doctype.unit.unit import sync_unit_listing
from pms.pms.doctype.move_in.move_in import fill_checklist_from_template, validate_checklist_attachments


class MoveOut(Document):

    def validate(self):
        self.validate_unit_on_lease()
        fill_checklist_from_template(self)
        validate_checklist_attachments(self)

    def before_update_after_submit(self):
        validate_checklist_attachments(self)

    def validate_unit_on_lease(self):
        if not (self.lease and self.unit):
            return
        lease_units = frappe.get_all(
            "Lease Agreement Unit", filters={"parent": self.lease}, pluck="unit_id"
        )
        if self.unit not in lease_units:
            frappe.throw(
                f"Unit <b>{self.unit}</b> is not part of Lease Agreement <b>{self.lease}</b>."
            )

    def on_update(self):
        """Notice is given the moment this draft exists with a notice_date
        (before the actual move-out submission) — mark the lease and put
        the unit back on the market immediately, even though the tenant
        is still living there."""
        if self.docstatus == 0 and self.notice_date:
            frappe.db.set_value("Lease Agreement", self.lease, "status", "Notice Given")
            unit_status = frappe.db.get_value("Unit", self.unit, "status")
            if unit_status == "Occupied":
                frappe.db.set_value("Unit", self.unit, "status", "Notice Given")
                sync_unit_listing(self.unit, "Notice Given")

    def on_cancel(self):
        if self.settlement and frappe.db.get_value("Security Deposit Settlement", self.settlement, "docstatus") == 0:
            frappe.delete_doc("Security Deposit Settlement", self.settlement, ignore_permissions=True)
            self.db_set("settlement", None)
