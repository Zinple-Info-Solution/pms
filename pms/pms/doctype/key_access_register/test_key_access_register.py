# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestKeyAccessRegister(FrappeTestCase):

    def setUp(self):
        if not frappe.db.exists("Property", "Test Key Property"):
            frappe.get_doc({"doctype": "Property", "building_name": "Test Key Property", "status": "Available"}).insert()
        if not frappe.db.exists("Unit", {"property": "Test Key Property"}):
            frappe.get_doc({"doctype": "Unit", "property": "Test Key Property", "monthly_rent": 5000}).insert()

    def test_status_derived_from_returned_date(self):
        unit = frappe.db.get_value("Unit", {"property": "Test Key Property"}, "name")
        key = frappe.get_doc({
            "doctype": "Key Access Register",
            "unit": unit,
            "holder_name": "Test Tenant",
        }).insert()
        self.addCleanup(lambda: frappe.delete_doc("Key Access Register", key.name, force=True))
        self.assertEqual(key.status, "Issued")

        key.returned_date = frappe.utils.today()
        key.save()
        self.assertEqual(key.status, "Returned")
