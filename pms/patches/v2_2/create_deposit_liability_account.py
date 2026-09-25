# Copyright (c) 2026, admin and contributors
"""Phase 3: create the "Tenant Security Deposits" liability account (per
company) that Security Deposit Settlement books deductions/refunds
against. Idempotent — skipped if the account already exists.
"""

import frappe

ACCOUNT_NAME = "Tenant Security Deposits"


def execute():
    for company in frappe.get_all("Company", pluck="name"):
        abbr = frappe.get_cached_value("Company", company, "abbr")
        account_name = f"{ACCOUNT_NAME} - {abbr}"
        if frappe.db.exists("Account", account_name):
            continue

        parent = frappe.db.get_value(
            "Account",
            {"company": company, "account_name": "Current Liabilities", "is_group": 1},
            "name",
        )
        if not parent:
            frappe.log_error(
                title="PMS Deposit Liability Account",
                message=f"No 'Current Liabilities' group account found for company {company}; skipped.",
            )
            continue

        frappe.get_doc({
            "doctype": "Account",
            "account_name": ACCOUNT_NAME,
            "company": company,
            "parent_account": parent,
            # account_type "Receivable" (not "Payable") so Journal Entry /
            # Payment Entry rows can carry party_type="Customer" against it
            # for per-tenant deposit tracking, even though it behaves as a
            # liability (credit balance) in practice.
            "account_type": "Receivable",
            "root_type": "Liability",
            "is_group": 0,
        }).insert(ignore_permissions=True)

    frappe.db.commit()
