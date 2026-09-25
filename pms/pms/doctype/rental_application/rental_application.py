# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import add_years, today


class RentalApplication(Document):

    @frappe.whitelist()
    def create_lease(self):
        if self.status != "Approved":
            frappe.throw("Only an Approved application can create a lease.")
        if self.lease:
            frappe.throw(f"Lease <b>{self.lease}</b> already exists for this application.")

        unit = frappe.get_doc("Unit", self.unit)

        tenant_name = frappe.db.get_value("Tenant", {"full_name": self.applicant_name}, "name")
        if not tenant_name:
            tenant = frappe.get_doc({
                "doctype": "Tenant",
                "full_name": self.applicant_name,
                "email": self.applicant_email,
                "mobile_no": self.applicant_phone or "0000000000",
            })
            tenant.insert(ignore_permissions=True)
            tenant_name = tenant.name

        lease = frappe.get_doc({
            "doctype": "Lease Agreement",
            "tenant": tenant_name,
            "building": unit.property,
            "lease_based_on": "Selected Units",
            "billing_based_on": "Asset Wise",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "units": [{"unit_id": unit.name}],
        })
        lease.insert(ignore_permissions=True)
        self.db_set("lease", lease.name)

        frappe.msgprint(
            f"Draft Lease <b>{lease.name}</b> created with a default 1-year term "
            f"starting today — adjust the dates before submitting.",
            indicator="green",
        )
        return lease.name
