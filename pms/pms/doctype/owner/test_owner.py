# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestOwner(FrappeTestCase):

    def test_supplier_auto_created(self):
        owner = frappe.get_doc({
            "doctype": "Owner",
            "owner_name": "Test Owner PMS",
            "mobile_no": "9999900010",
        }).insert()
        owner.reload()
        self.assertTrue(owner.supplier)
        self.assertTrue(frappe.db.exists("Supplier", owner.supplier))
        owner.delete()
