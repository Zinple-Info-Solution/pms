# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestInspection(FrappeTestCase):

    def setUp(self):
        if not frappe.db.exists("Property", "Test Inspection Property"):
            frappe.get_doc({
                "doctype": "Property", "building_name": "Test Inspection Property", "status": "Available",
            }).insert()
        if not frappe.db.exists("Unit", {"property": "Test Inspection Property"}):
            frappe.get_doc({
                "doctype": "Unit", "property": "Test Inspection Property", "monthly_rent": 5000,
            }).insert()
        if not frappe.db.exists("Inspection Template", "Test Move-In Checklist"):
            frappe.get_doc({
                "doctype": "Inspection Template",
                "template_name": "Test Move-In Checklist",
                "items": [{"item_name": "Kitchen"}, {"item_name": "Bathroom"}],
            }).insert()

    def test_prefill_from_template(self):
        unit = frappe.db.get_value("Unit", {"property": "Test Inspection Property"}, "name")
        inspection = frappe.get_doc({
            "doctype": "Inspection",
            "unit": unit,
            "template": "Test Move-In Checklist",
        }).insert()
        self.addCleanup(lambda: frappe.delete_doc("Inspection", inspection.name, force=True))
        self.assertEqual(len(inspection.findings), 2)
        self.assertEqual(inspection.findings[0].condition, "Good")
