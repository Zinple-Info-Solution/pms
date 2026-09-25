# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import add_years, today, flt


class RentalApplication(Document):

    def validate(self):
        self.calculate_screening_score()

    def calculate_screening_score(self):
        """Automatic pre-screen: income ratio (target >= 3x rent), ID
        documents on file, and at least one reference. This is a
        decision-support number for the Property Manager, not a hard
        gate — approval always stays a human Workflow action."""
        rent = frappe.db.get_value("Unit", self.unit, "monthly_rent") if self.unit else 0
        self.income_ratio = (flt(self.monthly_income) / flt(rent)) if rent else 0

        checks_passed = 0
        checks_total = 3

        if self.income_ratio >= 3:
            checks_passed += 1
        if self.get("documents"):
            checks_passed += 1
        if self.get("application_references"):
            checks_passed += 1

        if checks_passed == checks_total:
            self.screening_score = "Strong"
        elif checks_passed >= 1:
            self.screening_score = "Needs Review"
        else:
            self.screening_score = "Weak"

    def on_update(self):
        if self.status == "Rejected":
            self.maybe_send_rejection_email()

    def maybe_send_rejection_email(self):
        if not self.applicant_email or self.rejection_email_sent:
            return
        try:
            frappe.sendmail(
                recipients=[self.applicant_email],
                subject="Update on your rental application",
                message=(
                    f"<p>Thank you for your interest. After review, we are unable to "
                    f"move forward with your application for Unit {self.unit} at this time.</p>"
                ),
                delayed=True,
            )
            self.db_set("rejection_email_sent", 1)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Rejection email failed: {self.name}")

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
