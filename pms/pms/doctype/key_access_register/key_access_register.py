# Copyright (c) 2026, admin and contributors
from frappe.model.document import Document


class KeyAccessRegister(Document):

    def validate(self):
        self.status = "Returned" if self.returned_date else "Issued"
