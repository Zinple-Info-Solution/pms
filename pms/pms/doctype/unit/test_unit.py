# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestUnit(FrappeTestCase):

    def setUp(self):
        if not frappe.db.exists("Property", "Test Unit Property"):
            frappe.get_doc({
                "doctype": "Property",
                "building_name": "Test Unit Property",
                "status": "Available",
            }).insert()

    def test_facility_monthly_total_only_counts_ticked_recurring(self):
        if not frappe.db.exists("Property Facility", "Test Recurring Facility"):
            frappe.get_doc({
                "doctype": "Property Facility",
                "facility": "Test Recurring Facility",
                "charge_type": "Recurring",
                "default_amount": 500,
            }).insert()
        if not frappe.db.exists("Property Facility", "Test One Time Facility"):
            frappe.get_doc({
                "doctype": "Property Facility",
                "facility": "Test One Time Facility",
                "charge_type": "One Time",
                "default_amount": 2000,
            }).insert()

        unit = frappe.get_doc({
            "doctype": "Unit",
            "property": "Test Unit Property",
            "monthly_rent": 10000,
            "facilities": [
                {"facilities": "Test Recurring Facility", "value": 1, "charge_type": "Recurring", "amount": 500},
                {"facilities": "Test One Time Facility", "value": 1, "charge_type": "One Time", "amount": 2000},
                {"facilities": "Test Recurring Facility", "value": 0, "charge_type": "Recurring", "amount": 500},
            ],
        }).insert()
        self.addCleanup(lambda: frappe.delete_doc("Unit", unit.name, force=True))

        self.assertEqual(unit.facility_monthly_total, 500)
