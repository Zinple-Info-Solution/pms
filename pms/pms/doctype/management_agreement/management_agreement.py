# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class ManagementAgreement(Document):

    def validate(self):
        if self.fee_type == "Percent of Collected Rent" and not self.fee_percent:
            frappe.throw("Fee Percent is required for a Percent of Collected Rent fee type.")
        if self.fee_type == "Flat Monthly" and not self.fee_amount:
            frappe.throw("Fee Amount is required for a Flat Monthly fee type.")
