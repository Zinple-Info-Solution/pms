# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class MoveIn(Document):

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
