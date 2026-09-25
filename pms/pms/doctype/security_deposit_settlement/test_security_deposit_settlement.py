# Copyright (c) 2026, admin and contributors
import frappe
from frappe.tests.utils import FrappeTestCase


class TestSecurityDepositSettlement(FrappeTestCase):

    def test_totals_computed_on_save(self):
        settlement = frappe.get_doc({
            "doctype": "Security Deposit Settlement",
            "deposit_amount": 50000,
            "deductions": [
                {"reason": "Damage", "deduction_type": "Damage", "amount": 8000},
                {"reason": "Cleaning", "deduction_type": "Cleaning", "amount": 2000},
            ],
        })
        settlement.calculate_totals()
        self.assertEqual(settlement.total_deductions, 10000)
        self.assertEqual(settlement.refund_amount, 40000)

    def test_deductions_can_exceed_deposit(self):
        settlement = frappe.get_doc({
            "doctype": "Security Deposit Settlement",
            "deposit_amount": 10000,
            "deductions": [
                {"reason": "Damage", "deduction_type": "Damage", "amount": 15000},
            ],
        })
        settlement.calculate_totals()
        self.assertEqual(settlement.refund_amount, -5000)
