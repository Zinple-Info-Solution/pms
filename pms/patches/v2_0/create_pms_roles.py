# Copyright (c) 2026, admin and contributors
"""Phase 1: create the base PMS roles before doctype permissions are synced
(this must run pre_model_sync — the new/updated doctypes' permission rows
reference these roles by name)."""

import frappe

ROLES = ["Property Manager", "Leasing Agent", "Accountant", "Maintenance Staff"]


def execute():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1,
            }).insert(ignore_permissions=True)
    frappe.db.commit()
