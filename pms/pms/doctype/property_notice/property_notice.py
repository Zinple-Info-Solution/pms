# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PropertyNotice(Document):

    @frappe.whitelist()
    def send(self):
        if self.sent_date:
            frappe.throw("This notice has already been sent.")

        filters = {"docstatus": 1, "status": "Active"}
        if self.property:
            filters["building"] = self.property

        tenants = frappe.get_all("Lease Agreement", filters=filters, pluck="tenant")
        emails = list({
            e for e in frappe.get_all("Tenant", filters={"name": ["in", tenants]}, pluck="email") if e
        })

        if emails and self.sent_via in ("Email", "Both"):
            frappe.sendmail(
                recipients=emails,
                subject=self.subject,
                message=self.body,
                delayed=True,
            )

        self.db_set("sent_date", now_datetime())
        self.db_set("recipients_count", len(emails))
        return len(emails)
