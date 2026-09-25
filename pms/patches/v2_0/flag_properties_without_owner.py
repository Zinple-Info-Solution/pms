# Copyright (c) 2026, admin and contributors
"""Phase 1: Property Owner backfill.

No Owner concept existed before this rewrite, so there is no source data to
mechanically derive real owner names/shares from. This patch deliberately
does NOT fabricate placeholder Owner records — doing so would pollute
production data with fake owners. Instead it logs every Property that has
no Property Owner row yet, so an operator can create real Owner records and
populate Property.owners manually (or via a reviewed CSV import) before
Phase 6's Owner Statements are relied upon.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Property"):
        return

    properties = frappe.get_all("Property", pluck="name")
    without_owner = [
        p for p in properties
        if not frappe.db.exists("Property Owner", {"parenttype": "Property", "parent": p})
    ]

    if without_owner:
        frappe.log_error(
            title="PMS Property Owner Backfill",
            message=(
                f"{len(without_owner)} Property record(s) have no owner assigned yet: "
                f"{', '.join(without_owner)}. Add Owner records and populate the "
                f"Property > Owners table manually before relying on Owner Statements."
            ),
        )
