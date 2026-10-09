# Copyright (c) 2026, admin and contributors
"""Facility Ops (Cleaning/Security/Parking/Waste): create the one new role
these doctypes need — Security Staff for Security Incident. Cleaning and
Waste Collection tasks reuse the existing Maintenance Staff role. Runs
pre_model_sync, same as create_pms_roles — the new doctypes' permission
rows reference this role by name."""

import frappe

ROLES = ["Security Staff"]


def execute():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1,
            }).insert(ignore_permissions=True)
    frappe.db.commit()
