# Copyright (c) 2026, admin and contributors
"""Property Profitability: per-property Profit & Loss (rent + utility income
collected vs. cost-center expenses) for a date range, compared against any
overlapping Property Budget."""

import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw("Please set both From Date and To Date.")
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "property", "label": "Property", "fieldtype": "Link",
         "options": "Property", "width": 150},
        {"fieldname": "income", "label": "Income (Collected)", "fieldtype": "Currency", "width": 140},
        {"fieldname": "expense", "label": "Expense", "fieldtype": "Currency", "width": 120},
        {"fieldname": "net", "label": "Net", "fieldtype": "Currency", "width": 120},
        {"fieldname": "budgeted_income", "label": "Budgeted Income", "fieldtype": "Currency", "width": 140},
        {"fieldname": "budgeted_expense", "label": "Budgeted Expense", "fieldtype": "Currency", "width": 140},
        {"fieldname": "income_variance", "label": "Income Variance", "fieldtype": "Currency", "width": 130},
        {"fieldname": "expense_variance", "label": "Expense Variance", "fieldtype": "Currency", "width": 130},
    ]


def get_data(filters):
    property_filters = {}
    if filters.get("property"):
        property_filters["name"] = filters["property"]

    properties = frappe.get_all(
        "Property", filters=property_filters, fields=["name", "cost_center"]
    )

    rows = []
    for prop in properties:
        income = get_income(prop.name, filters["from_date"], filters["to_date"])
        expense = get_expense(prop.cost_center, filters["from_date"], filters["to_date"])
        budgeted_income, budgeted_expense = get_budget(
            prop.name, filters["from_date"], filters["to_date"]
        )
        rows.append({
            "property": prop.name,
            "income": income,
            "expense": expense,
            "net": flt(income) - flt(expense),
            "budgeted_income": budgeted_income,
            "budgeted_expense": budgeted_expense,
            "income_variance": flt(income) - flt(budgeted_income),
            "expense_variance": flt(expense) - flt(budgeted_expense),
        })
    return rows


def get_income(property_name, from_date, to_date):
    """Rent + utility payments collected against this property's invoices."""
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(per.allocated_amount), 0)
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
        WHERE per.reference_doctype = 'Sales Invoice'
          AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND (
            per.reference_name IN (
                SELECT rs.sales_invoice FROM `tabRent Schedule` rs
                INNER JOIN `tabLease Agreement` la ON la.name = rs.parent
                WHERE la.building = %(property)s
                  AND rs.sales_invoice IS NOT NULL AND rs.sales_invoice != ''
            )
            OR per.reference_name IN (
                SELECT mr.sales_invoice FROM `tabMeter Reading` mr
                INNER JOIN `tabUtility Meter` um ON um.name = mr.meter
                WHERE um.property = %(property)s
                  AND mr.sales_invoice IS NOT NULL AND mr.sales_invoice != ''
            )
          )
        """,
        {"property": property_name, "from_date": from_date, "to_date": to_date},
    )
    return flt(val[0][0]) if val else 0.0


def get_expense(cost_center, from_date, to_date):
    if not cost_center:
        return 0.0
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(pii.base_net_amount), 0)
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE pii.cost_center = %(cost_center)s
          AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
        """,
        {"cost_center": cost_center, "from_date": from_date, "to_date": to_date},
    )
    return flt(val[0][0]) if val else 0.0


def get_budget(property_name, from_date, to_date):
    row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(budgeted_income), 0), COALESCE(SUM(budgeted_expense), 0)
        FROM `tabProperty Budget`
        WHERE property = %(property)s
          AND period_start <= %(to_date)s
          AND period_end >= %(from_date)s
        """,
        {"property": property_name, "from_date": from_date, "to_date": to_date},
    )
    if not row:
        return 0.0, 0.0
    return flt(row[0][0]), flt(row[0][1])
