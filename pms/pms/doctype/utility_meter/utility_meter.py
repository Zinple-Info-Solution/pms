# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class UtilityMeter(Document):

    def validate(self):
        if self.unit:
            unit_property = frappe.db.get_value("Unit", self.unit, "property")
            if unit_property and unit_property != self.property:
                self.property = unit_property
