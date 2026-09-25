# Copyright (c) 2026, admin and contributors
from frappe.model.document import Document
from frappe.utils import flt


class SecurityDepositSettlement(Document):

    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        self.total_deductions = sum(flt(d.amount) for d in (self.deductions or []))
        self.refund_amount = flt(self.deposit_amount) - flt(self.total_deductions)

    def on_submit(self):
        from pms.pms.billing import settle_security_deposit
        settle_security_deposit(self)
