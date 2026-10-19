# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from pms.pms.doctype.unit.unit import sync_unit_listing


class MoveIn(Document):

    def validate(self):
        self.validate_unit_on_lease()
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

    def on_submit(self):
        from pms.pms.doctype.lease_agreement.lease_agreement import log_occupancy_event
        from pms.pms.portal import invite_tenant_to_portal

        frappe.db.set_value("Unit", self.unit, "status", "Occupied")
        sync_unit_listing(self.unit, "Occupied")
        log_occupancy_event(self.unit, "Occupied", lease=self.lease)

        if self.tenant:
            invite_tenant_to_portal(self.tenant)

    def on_cancel(self):
        frappe.db.set_value("Unit", self.unit, "status", "Reserved")
        sync_unit_listing(self.unit, "Reserved")


def validate_checklist_attachments(doc):
    """Shared by Move In and Move Out: every row of the Attachments table
    must point at an item that's actually on this document's checklist."""
    items = {row.item for row in doc.condition_checklist or []}
    for row in doc.attachments or []:
        if row.item not in items:
            frappe.throw(
                f"Attachments row #{row.idx}: <b>{row.item}</b> is not an item "
                f"on the condition checklist."
            )
