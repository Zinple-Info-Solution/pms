# Copyright (c) 2026, admin and contributors
"""Phase 1 bug fix: Maintenance Request.tenant used to link to Customer,
inconsistent with the rest of the app (Lease Agreement, Service Apartment
Booking both link to Tenant). Re-point existing values via the reverse
Tenant.customer lookup. Requests whose Customer has no matching Tenant are
left as-is and flagged for manual review.
"""

import frappe


def execute():
    if not (frappe.db.exists("DocType", "Maintenance Request") and frappe.db.exists("DocType", "Tenant")):
        return

    rows = frappe.get_all("Maintenance Request", fields=["name", "tenant"])
    unresolved = []

    for row in rows:
        if not row.tenant:
            continue
        if frappe.db.exists("Tenant", row.tenant):
            # Already a Tenant name (e.g. a fresh record created after this
            # patch already ran once) — nothing to do.
            continue

        tenant_name = frappe.db.get_value("Tenant", {"customer": row.tenant}, "name")
        if tenant_name:
            frappe.db.set_value("Maintenance Request", row.name, "tenant", tenant_name)
        else:
            unresolved.append(row.name)

    frappe.db.commit()

    if unresolved:
        frappe.log_error(
            title="PMS Maintenance Request Tenant Repoint",
            message=(
                f"Maintenance Request(s) with no matching Tenant for their Customer, "
                f"left unresolved for manual review: {', '.join(unresolved)}"
            ),
        )
