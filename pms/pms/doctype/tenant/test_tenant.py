# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestTenant(FrappeTestCase):

    def test_customer_auto_created(self):
        tenant = frappe.get_doc({
            "doctype": "Tenant",
            "full_name": "Test Tenant PMS",
            "mobile_no": "9999900001",
        }).insert()
        tenant.reload()
        self.assertTrue(tenant.customer)
        self.assertTrue(frappe.db.exists("Customer", tenant.customer))
        tenant.delete()

    def test_duplicate_mobile_blocked(self):
        t1 = frappe.get_doc({
            "doctype": "Tenant",
            "full_name": "Tenant One PMS",
            "mobile_no": "9999900002",
        }).insert()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Tenant",
                "full_name": "Tenant Two PMS",
                "mobile_no": "9999900002",
            }).insert()

        t1.delete()
