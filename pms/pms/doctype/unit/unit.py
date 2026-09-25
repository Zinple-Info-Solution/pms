# Copyright (c) 2026, admin and contributors
import frappe
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

    def on_update(self):
        previous = self.get_doc_before_save()
        if not previous or previous.status != self.status:
            sync_unit_listing(self.name, self.status)


def sync_unit_listing(unit_name, new_status):
    """Publish (or unpublish) a Unit Listing to match a Unit's status.

    Called explicitly from every place that changes Unit.status —
    including the many call sites that use frappe.db.set_value() directly
    for performance rather than loading and saving the full Document
    (which is what most of this app's occupancy-changing code does), and
    which therefore never fires Unit.on_update() on its own."""
    if new_status in ("Vacant", "Notice Given"):
        existing = frappe.db.get_value("Unit Listing", {"unit": unit_name}, "name")
        if existing:
            frappe.db.set_value("Unit Listing", existing, "is_active", 1)
        else:
            frappe.get_doc({
                "doctype": "Unit Listing",
                "unit": unit_name,
                "is_active": 1,
            }).insert(ignore_permissions=True)
    elif new_status in ("Reserved", "Occupied"):
        # Off the market the moment it's spoken for (lease signed), not
        # only once the tenant has actually moved in.
        frappe.db.set_value(
            "Unit Listing", {"unit": unit_name, "is_active": 1}, "is_active", 0
        )
