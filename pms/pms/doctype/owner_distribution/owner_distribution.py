# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class OwnerDistribution(Document):

    def on_submit(self):
        self.create_payment_entry()

    def create_payment_entry(self):
        owner = frappe.get_doc("Owner", self.owner_id)
        if not owner.supplier:
            frappe.throw(f"Owner <b>{owner.owner_name}</b> has no linked Supplier.")

        company = frappe.db.get_single_value("Global Defaults", "default_company")
        bank_or_cash = (
            frappe.get_cached_value("Company", company, "default_bank_account")
            or frappe.get_cached_value("Company", company, "default_cash_account")
        )

        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Pay",
            "party_type": "Supplier",
            "party": owner.supplier,
            "paid_from": bank_or_cash,
            "paid_to": frappe.get_cached_value(
                "Company", company, "default_payable_account"
            ),
            "paid_amount": flt(self.amount),
            "received_amount": flt(self.amount),
            "reference_no": self.name,
            "reference_date": frappe.utils.today(),
            "remarks": f"Owner distribution for {self.property} — {self.owner_statement}",
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        self.db_set("payment_entry", pe.name)

        frappe.db.set_value("Owner Statement", self.owner_statement, "status", "Distributed")
