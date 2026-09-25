# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class Inspection(Document):

    def validate(self):
        if self.template and not self.findings:
            self.prefill_from_template()

    def prefill_from_template(self):
        template = frappe.get_doc("Inspection Template", self.template)
        for item in template.items:
            self.append("findings", {
                "item_name": item.item_name,
                "condition": "Good",
            })
