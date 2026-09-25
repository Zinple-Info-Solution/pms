# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class MoveOut(Document):

    def validate(self):
        self.validate_unit_on_lease()

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

    def on_cancel(self):
        if self.settlement and frappe.db.get_value("Security Deposit Settlement", self.settlement, "docstatus") == 0:
            frappe.delete_doc("Security Deposit Settlement", self.settlement, ignore_permissions=True)
            self.db_set("settlement", None)
