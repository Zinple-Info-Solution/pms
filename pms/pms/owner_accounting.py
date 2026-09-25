# Copyright (c) 2026, admin and contributors
# Owner Statement generation and Owner Distribution — trust accounting
# built entirely on ERPNext's own Sales Invoice / Purchase Invoice /
# Payment Entry / Cost Center primitives, per the "don't rebuild
# accounting" principle: a Property's Cost Center is the single source
# of truth for what income/expense belongs to it.

import frappe
from frappe.utils import flt, getdate


def populate_owner_statement(statement):
    """(Re)compute income_lines, expense_lines and the fee/distribution
    totals for an Owner Statement from GL activity in its period."""
    property_doc = frappe.get_doc("Property", statement.property)
    if not property_doc.cost_center:
        frappe.throw(
            f"Property <b>{property_doc.name}</b> has no Cost Center set — "
            f"save the Property once to auto-create one."
        )

    income_rows = frappe.db.sql("""
        SELECT si.posting_date, si.name, si.customer, sii.amount
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.cost_center = %(cost_center)s
          AND si.docstatus = 1
          AND si.posting_date BETWEEN %(start)s AND %(end)s
        ORDER BY si.posting_date
    """, {
        "cost_center": property_doc.cost_center,
        "start": statement.period_start,
        "end": statement.period_end,
    }, as_dict=True)

    expense_rows = frappe.db.sql("""
        SELECT pi.posting_date, pi.name, pi.supplier, pii.amount
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pii.cost_center = %(cost_center)s
          AND pi.docstatus = 1
          AND pi.posting_date BETWEEN %(start)s AND %(end)s
        ORDER BY pi.posting_date
    """, {
        "cost_center": property_doc.cost_center,
        "start": statement.period_start,
        "end": statement.period_end,
    }, as_dict=True)

    statement.set("income_lines", [{
        "posting_date": r.posting_date,
        "reference_doctype": "Sales Invoice",
        "reference_name": r.name,
        "description": f"Rent/charges — {r.customer}",
        "amount": r.amount,
    } for r in income_rows])

    statement.set("expense_lines", [{
        "posting_date": r.posting_date,
        "reference_doctype": "Purchase Invoice",
        "reference_name": r.name,
        "description": f"Vendor bill — {r.supplier}",
        "amount": r.amount,
    } for r in expense_rows])

    statement.gross_income = sum(flt(r.amount) for r in income_rows)
    statement.gross_expense = sum(flt(r.amount) for r in expense_rows)

    agreement = frappe.db.get_value(
        "Management Agreement",
        {"property": property_doc.name, "owner_id": statement.owner_id},
        ["fee_type", "fee_percent", "fee_amount", "reserve_amount"],
        as_dict=True,
    )
    if agreement:
        if agreement.fee_type == "Percent of Collected Rent":
            statement.management_fee = flt(statement.gross_income) * flt(agreement.fee_percent) / 100
        else:
            statement.management_fee = flt(agreement.fee_amount)
        statement.reserve_held = flt(agreement.reserve_amount)
    else:
        statement.management_fee = 0
        statement.reserve_held = 0

    statement.net_distributable = (
        flt(statement.gross_income)
        - flt(statement.gross_expense)
        - flt(statement.management_fee)
        - flt(statement.reserve_held)
    )
    if statement.status == "Draft":
        statement.status = "Finalized"


def generate_monthly_owner_statements():
    """Runs monthly: auto-generate an Owner Statement for the prior month
    for every (Property, Owner) pair on record, skipping any period
    that's already been generated."""
    from frappe.utils import add_months, get_first_day, get_last_day

    period_start = get_first_day(add_months(getdate(), -1))
    period_end = get_last_day(period_start)

    pairs = frappe.db.sql("""
        SELECT po.parent AS property, po.owner_id
        FROM `tabProperty Owner` po
        WHERE po.parenttype = 'Property'
    """, as_dict=True)

    for pair in pairs:
        exists = frappe.db.exists("Owner Statement", {
            "property": pair.property,
            "owner_id": pair.owner_id,
            "period_start": period_start,
            "period_end": period_end,
        })
        if exists:
            continue

        try:
            statement = frappe.get_doc({
                "doctype": "Owner Statement",
                "owner_id": pair.owner_id,
                "property": pair.property,
                "period_start": period_start,
                "period_end": period_end,
            })
            statement.insert(ignore_permissions=True)
            statement.generate()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Owner Statement generation failed: {pair.property} / {pair.owner_id}",
            )


def create_distribution(owner_statement_name):
    """Create (and submit) an Owner Distribution + Payment Entry paying out
    an Owner Statement's net_distributable amount to the owner's Supplier."""
    statement = frappe.get_doc("Owner Statement", owner_statement_name)
    if flt(statement.net_distributable) <= 0:
        frappe.throw("Nothing to distribute: Net Distributable is zero or negative.")

    owner = frappe.get_doc("Owner", statement.owner_id)
    if not owner.supplier:
        frappe.throw(f"Owner <b>{owner.owner_name}</b> has no linked Supplier.")

    distribution = frappe.get_doc({
        "doctype": "Owner Distribution",
        "owner_statement": statement.name,
        "amount": statement.net_distributable,
    })
    distribution.insert(ignore_permissions=True)
    distribution.submit()
    return distribution.name
