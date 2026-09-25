# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestLateFeeRule(FrappeTestCase):

    def test_flat_requires_fee_amount(self):
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Late Fee Rule",
                "grace_period_days": 5,
                "fee_type": "Flat",
            }).insert()

    def test_percent_requires_fee_percent(self):
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Late Fee Rule",
                "grace_period_days": 5,
                "fee_type": "Percent of Rent",
            }).insert()
