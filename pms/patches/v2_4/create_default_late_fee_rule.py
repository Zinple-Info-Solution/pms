# Copyright (c) 2026, admin and contributors
"""Phase 5: seed a single site-wide default Late Fee Rule (5-day grace,
flat fee) so apply_late_fees() has a fallback rule rather than silently
doing nothing on every property. Idempotent — skipped if any Late Fee
Rule already exists."""

import frappe


def execute():
    if frappe.db.exists("DocType", "Late Fee Rule") and not frappe.db.exists("Late Fee Rule"):
        frappe.get_doc({
            "doctype": "Late Fee Rule",
            "property": None,
            "is_active": 1,
            "grace_period_days": 5,
            "fee_type": "Flat",
            "fee_amount": 500,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
