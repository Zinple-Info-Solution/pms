# Copyright (c) 2026, admin and contributors
"""Phase 6: create a Management Agreement for every (Property, Property
Owner) pair on record, so Owner Statement generation has fee terms to
read. fee_percent is seeded at 0 as an explicitly-flagged placeholder —
this is not a business decision, real fee terms must be entered
manually. Also copies the Property-level Maintenance Approval Limit
(from Phase 4) into the agreement, since it's now the authoritative
source for that.

Idempotent per (property, owner) pair.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Management Agreement"):
        return

    pairs = frappe.db.sql("""
        SELECT po.parent AS property, po.owner_id
        FROM `tabProperty Owner` po
        WHERE po.parenttype = 'Property'
    """, as_dict=True)

    if not pairs:
        return

    created = 0
    for pair in pairs:
        if frappe.db.exists("Management Agreement", {"property": pair.property, "owner_id": pair.owner_id}):
            continue

        approval_limit = frappe.db.get_value("Property", pair.property, "maintenance_approval_limit")

        frappe.get_doc({
            "doctype": "Management Agreement",
            "property": pair.property,
            "owner_id": pair.owner_id,
            "fee_type": "Percent of Collected Rent",
            "fee_percent": 0,
            "approval_limit": approval_limit or 0,
        }).insert(ignore_permissions=True)
        created += 1

    frappe.db.commit()

    if created:
        frappe.log_error(
            title="PMS Management Agreement Backfill",
            message=(
                f"{created} Management Agreement(s) created with fee_percent=0 "
                f"as a placeholder. Update with real fee terms before relying "
                f"on Owner Statements."
            ),
        )
