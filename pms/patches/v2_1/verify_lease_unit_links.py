# Copyright (c) 2026, admin and contributors
"""Phase 2 sanity check (non-mutating): confirm every active Lease
Agreement's units resolve to real Unit documents whose status is
consistent with the lease being Active, before billing logic starts
running against them. Logs findings only, never writes.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Unit"):
        return

    dangling = frappe.db.sql("""
        SELECT lau.parent AS lease, lau.unit_id
        FROM `tabLease Agreement Unit` lau
        INNER JOIN `tabLease Agreement` la ON la.name = lau.parent
        LEFT JOIN `tabUnit` u ON u.name = lau.unit_id
        WHERE la.docstatus = 1 AND la.status = 'Active' AND u.name IS NULL
    """, as_dict=True)

    inconsistent = frappe.db.sql("""
        SELECT lau.parent AS lease, lau.unit_id, u.status
        FROM `tabLease Agreement Unit` lau
        INNER JOIN `tabLease Agreement` la ON la.name = lau.parent
        INNER JOIN `tabUnit` u ON u.name = lau.unit_id
        WHERE la.docstatus = 1 AND la.status = 'Active' AND u.status != 'Occupied'
    """, as_dict=True)

    if dangling:
        frappe.log_error(
            title="PMS Lease/Unit Link Check: dangling references",
            message="\n".join(f"{d.lease} -> missing Unit {d.unit_id}" for d in dangling),
        )
    if inconsistent:
        frappe.log_error(
            title="PMS Lease/Unit Link Check: status inconsistency",
            message="\n".join(
                f"{d.lease} -> Unit {d.unit_id} is {d.status}, expected Occupied"
                for d in inconsistent
            ),
        )
