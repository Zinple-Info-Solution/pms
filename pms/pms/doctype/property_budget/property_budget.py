# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class PropertyBudget(Document):

    def validate(self):
        if getdate(self.period_end) < getdate(self.period_start):
            frappe.throw("Period End cannot be before Period Start.")
