# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class ParkingSlot(Document):

    def validate(self):
        if self.status == "Allocated" and not (self.allocated_to_type and self.allocated_to):
            frappe.throw("Set Allocated To Type and Allocated To before marking this slot Allocated.")
