# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class OwnerStatement(Document):

    @frappe.whitelist()
    def generate(self):
        from pms.pms.owner_accounting import populate_owner_statement
        populate_owner_statement(self)
        self.save()
        return self.name
