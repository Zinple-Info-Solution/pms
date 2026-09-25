# Copyright (c) 2026, admin and contributors
"""Rent Roll: one row per Unit showing its current occupancy, lease, tenant
and next rent due date/status — the standard property-management snapshot
of "what's owed and by whom, unit by unit"."""

import frappe


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "unit", "label": "Unit", "fieldtype": "Link",
         "options": "Unit", "width": 130},
        {"fieldname": "property", "label": "Property", "fieldtype": "Link",
         "options": "Property", "width": 150},
        {"fieldname": "unit_type", "label": "Unit Type", "fieldtype": "Link",
         "options": "Unit Type", "width": 120},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
        {"fieldname": "monthly_rent", "label": "Monthly Rent", "fieldtype": "Currency", "width": 120},
        {"fieldname": "lease", "label": "Lease", "fieldtype": "Link",
         "options": "Lease Agreement", "width": 150},
        {"fieldname": "tenant", "label": "Tenant", "fieldtype": "Link",
         "options": "Tenant", "width": 140},
        {"fieldname": "next_due_date", "label": "Next Due Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "next_due_status", "label": "Next Due Status", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    conditions = ["1=1"]
    values = {}

    if filters.get("property"):
        conditions.append("u.property = %(property)s")
        values["property"] = filters["property"]
    if filters.get("status"):
        conditions.append("u.status = %(status)s")
        values["status"] = filters["status"]

    rows = frappe.db.sql(f"""
        SELECT
            u.name AS unit, u.property, u.unit_type, u.status, u.monthly_rent,
            la.name AS lease, la.tenant
        FROM `tabUnit` u
        LEFT JOIN `tabLease Agreement Unit` lau ON lau.unit_id = u.name
        LEFT JOIN `tabLease Agreement` la
            ON la.name = lau.parent AND la.docstatus = 1 AND la.status = 'Active'
        WHERE {' AND '.join(conditions)}
        ORDER BY u.property, u.name
    """, values, as_dict=True)

    lease_names = [r.lease for r in rows if r.lease]
    next_due = {}
    if lease_names:
        due_rows = frappe.db.sql("""
            SELECT parent, due_date, status
            FROM `tabRent Schedule`
            WHERE parent IN %(leases)s AND status = 'Pending'
            ORDER BY due_date ASC
        """, {"leases": lease_names}, as_dict=True)
        for d in due_rows:
            next_due.setdefault(d.parent, d)

    for r in rows:
        due = next_due.get(r.lease)
        r.next_due_date = due.due_date if due else None
        r.next_due_status = due.status if due else ("—" if not r.lease else "Fully Invoiced")

    return rows
