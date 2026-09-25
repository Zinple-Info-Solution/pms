# Copyright (c) 2026, admin and contributors
"""Phase 2: Sales Invoice Item.custom_unit_type changed from a hardcoded
Select ("Apartment"/"Shop"/"Gym") to a real Link -> Unit Type. Existing
historical rows may hold a stored string that no longer resolves to a real
Unit Type record. This is read-only historical data (nothing re-validates
it retroactively), so this patch only logs affected rows for awareness —
it does not rewrite submitted financial documents.
"""

import frappe


def execute():
    if not frappe.db.has_column("Sales Invoice Item", "custom_unit_type"):
        return

    rows = frappe.db.sql("""
        SELECT sii.parent, sii.name, sii.custom_unit_type
        FROM `tabSales Invoice Item` sii
        WHERE sii.custom_unit_type IS NOT NULL AND sii.custom_unit_type != ''
          AND NOT EXISTS (
              SELECT 1 FROM `tabUnit Type` ut WHERE ut.name = sii.custom_unit_type
          )
    """, as_dict=True)

    if rows:
        frappe.log_error(
            title="PMS Sales Invoice Item unit_type unresolved",
            message="\n".join(
                f"{r.parent} / row {r.name}: '{r.custom_unit_type}' has no matching Unit Type"
                for r in rows
            ),
        )
