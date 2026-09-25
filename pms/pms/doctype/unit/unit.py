# Copyright (c) 2026, admin and contributors
from frappe.model.document import Document


class Unit(Document):

    def validate(self):
        self.calculate_facility_monthly_total()

    def calculate_facility_monthly_total(self):
        total = 0
        for row in self.get("facilities") or []:
            if row.value and row.charge_type == "Recurring":
                total += row.amount or 0
        self.facility_monthly_total = total
