# Copyright (c) 2026, admin and contributors
import frappe
from frappe.utils import today, date_diff, getdate


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "lease", "label": "Lease", "fieldtype": "Link",
         "options": "Lease Agreement", "width": 160},
        {"fieldname": "tenant", "label": "Tenant", "fieldtype": "Link",
         "options": "Tenant", "width": 140},
        {"fieldname": "building", "label": "Building", "fieldtype": "Link",
         "options": "Building", "width": 130},
        {"fieldname": "due_date", "label": "Due Date", "fieldtype": "Date", "width": 105},
        {"fieldname": "billing_period", "label": "Period", "fieldtype": "Data", "width": 180},
        {"fieldname": "total_amount", "label": "Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 90},
        {"fieldname": "overdue_days", "label": "Overdue (Days)", "fieldtype": "Int", "width": 120},
        {"fieldname": "sales_invoice", "label": "Invoice", "fieldtype": "Link",
         "options": "Sales Invoice", "width": 150},
    ]


def get_data(filters):
    conditions = ["la.docstatus = 1"]
    values = {}

    if filters.get("building"):
        conditions.append("la.building = %(building)s")
        values["building"] = filters["building"]
    if filters.get("status"):
        conditions.append("rs.status = %(status)s")
        values["status"] = filters["status"]
    if filters.get("tenant"):
        conditions.append("la.tenant = %(tenant)s")
        values["tenant"] = filters["tenant"]

    rows = frappe.db.sql(f"""
        SELECT
            la.name AS lease, la.tenant, la.building,
            rs.due_date, rs.billing_period, rs.total_amount,
            rs.status, rs.sales_invoice
        FROM `tabRent Schedule` rs
        INNER JOIN `tabLease Agreement` la ON la.name = rs.parent
        WHERE {' AND '.join(conditions)}
        ORDER BY rs.due_date ASC
    """, values, as_dict=True)

    for r in rows:
        r.overdue_days = (
            date_diff(getdate(today()), getdate(r.due_date))
            if r.status == "Pending" and getdate(r.due_date) < getdate(today())
            else 0
        )
    return rows
