# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class MaintenanceRequest(Document):

    def validate(self):
        self.validate_unit_belongs_to_building()
        self.set_resolution_timestamp()
        self.validate_resolution_details()

    def on_update(self):
        self.notify_assignee()

    # ------------------------------------------------------------
    # Validations
    # ------------------------------------------------------------
    def validate_unit_belongs_to_building(self):
        if not (self.unit and self.building):
            return

        asset_building = frappe.db.get_value("Asset", self.unit, "custom_building")
        if asset_building and asset_building != self.building:
            frappe.throw(
                f"Unit <b>{self.unit}</b> belongs to building "
                f"<b>{asset_building}</b>, not <b>{self.building}</b>."
            )

    def set_resolution_timestamp(self):
        if self.status in ("Resolved", "Closed") and not self.resolved_on:
            self.resolved_on = now_datetime()
        elif self.status not in ("Resolved", "Closed"):
            self.resolved_on = None

    def validate_resolution_details(self):
        if self.status in ("Resolved", "Closed") and not self.resolution_details:
            frappe.throw(
                "Please fill <b>Resolution Details</b> before marking "
                "the request as Resolved / Closed."
            )

    # ------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------
    def notify_assignee(self):
        """Notify the assigned user when assignment changes."""
        if not self.assigned_to:
            return

        old_assignee = None
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            old_assignee = old_doc.assigned_to if old_doc else None

        if self.assigned_to == old_assignee:
            return

        try:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Maintenance Request {self.name} assigned to you",
                "for_user": self.assigned_to,
                "type": "Assignment",
                "document_type": "Maintenance Request",
                "document_name": self.name,
                "email_content": (
                    f"<b>{self.subject}</b><br>"
                    f"Building: {self.building} | Unit: {self.unit}<br>"
                    f"Priority: {self.priority} | Type: {self.issue_type}"
                ),
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Maintenance Request notify failed: {self.name}",
            )
