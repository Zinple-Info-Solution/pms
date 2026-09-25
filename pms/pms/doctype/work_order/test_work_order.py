# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestWorkOrder(FrappeTestCase):

    def setUp(self):
        if not frappe.db.exists("Property", "Test Work Order Property"):
            frappe.get_doc({
                "doctype": "Property",
                "building_name": "Test Work Order Property",
                "status": "Available",
                "maintenance_approval_limit": 5000,
            }).insert()

    def test_approval_not_required_under_limit(self):
        wo = frappe.get_doc({
            "doctype": "Work Order",
            "property": "Test Work Order Property",
            "estimated_cost": 2000,
        })
        wo.insert()
        self.addCleanup(lambda: frappe.delete_doc("Work Order", wo.name, force=True))
        self.assertEqual(wo.approval_required, 0)

    def test_approval_required_over_limit(self):
        wo = frappe.get_doc({
            "doctype": "Work Order",
            "property": "Test Work Order Property",
            "estimated_cost": 9000,
        })
        wo.insert()
        self.addCleanup(lambda: frappe.delete_doc("Work Order", wo.name, force=True))
        self.assertEqual(wo.approval_required, 1)
