# Copyright (c) 2026, admin and contributors
"""Phase 6: Property.ensure_cost_center() only runs as an on_update() side
effect, so existing Properties from before this phase never got one
auto-created. Re-save each Property once to trigger it — needed before
Owner Statements can be generated for them."""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Property"):
        return

    for name in frappe.get_all("Property", filters={"cost_center": ["in", ["", None]]}, pluck="name"):
        try:
            frappe.get_doc("Property", name).save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Property cost center backfill failed: {name}",
            )

    frappe.db.commit()
