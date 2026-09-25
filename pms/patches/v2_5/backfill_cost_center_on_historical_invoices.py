# Copyright (c) 2026, admin and contributors
"""Phase 6: set cost_center on Sales Invoice Item / Purchase Invoice Item
rows created by earlier phases (rent invoices, vendor bills) before
billing.py started setting it on every new line, so Owner Statements
generated for past periods aren't missing income/expense.

This only touches cost_center — verified as allow_on_submit=1 on both
core doctypes, so updating it on already-submitted documents is within
what the doctype itself declares safe, not a validation bypass.

PMS rent invoice lines are identified via custom_lease_agreement being
set; vendor bill lines via remarks containing "Work Order:" (billing.py's
own convention — see create_vendor_bill()). Only rows with a blank
cost_center are touched.
"""

import frappe


def execute():
    if not frappe.db.has_column("Sales Invoice Item", "custom_lease_agreement"):
        return

    sales_rows = frappe.db.sql("""
        SELECT sii.name, la.building AS property
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabLease Agreement` la ON la.name = sii.custom_lease_agreement
        WHERE (sii.cost_center IS NULL OR sii.cost_center = '')
          AND sii.custom_lease_agreement IS NOT NULL AND sii.custom_lease_agreement != ''
    """, as_dict=True)

    updated = 0
    for r in sales_rows:
        cost_center = frappe.db.get_value("Property", r.property, "cost_center")
        if cost_center:
            frappe.db.set_value("Sales Invoice Item", r.name, "cost_center", cost_center)
            updated += 1

    purchase_rows = frappe.db.sql("""
        SELECT pii.name, pi.remarks
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE (pii.cost_center IS NULL OR pii.cost_center = '')
          AND pi.remarks LIKE 'Work Order:%'
    """, as_dict=True)

    for r in purchase_rows:
        try:
            property_name = r.remarks.split("Property:")[1].strip().splitlines()[0]
        except IndexError:
            continue
        cost_center = frappe.db.get_value("Property", property_name, "cost_center")
        if cost_center:
            frappe.db.set_value("Purchase Invoice Item", r.name, "cost_center", cost_center)
            updated += 1

    frappe.db.commit()

    if updated:
        frappe.log_error(
            title="PMS Cost Center Backfill",
            message=f"{updated} invoice line(s) backfilled with cost_center.",
        )
