# Copyright (c) 2026, admin and contributors
"""Phase 8: portal roles + User Permission wiring for Tenant/Owner/Vendor
self-service.

Creates three portal-only roles (Tenant, Owner, Vendor — desk_access=0)
and, for every Tenant/Owner whose email matches an *existing* Frappe
User, adds that user to the role and creates a User Permission scoping
them to their own Customer/Supplier record. Frappe's standard "Apply
User Permission" mechanism then automatically restricts every doctype
with a Link to Customer/Supplier (Lease Agreement, Sales Invoice, Owner
Statement's underlying Purchase Invoice, etc.) to that record.

Deliberately does NOT bulk-create login credentials for existing
tenants/owners without their consent — it only wires the permission
rule where a portal User already exists for that email. Inviting people
as portal users is a separate, explicit step (Frappe's own "Invite as
Portal User").
"""

import frappe

ROLES = ["Tenant", "Owner", "Vendor"]


def execute():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 0,
            }).insert(ignore_permissions=True)

    # Tenant portal users need restricting on BOTH Customer (Lease Agreement,
    # Sales Invoice) and Tenant itself (Maintenance Request.tenant).
    _wire_portal_users("Tenant", "email", [("Customer", "customer"), ("Tenant", "name")], "Tenant")
    _wire_portal_users("Owner", "email", [("Supplier", "supplier"), ("Owner", "name")], "Owner")
    # Vendors are plain Suppliers (no dedicated PMS doctype) — wire directly
    # off Supplier.email_id for any Supplier used as a Work Order vendor.
    _wire_portal_users("Supplier", "email_id", [("Supplier", "name")], "Vendor")

    frappe.db.commit()


def _wire_portal_users(source_doctype, email_field, restrictions, role):
    """restrictions: list of (allow_doctype, source_fieldname) pairs — each
    becomes one User Permission row scoping the matched User to that value."""
    fields = list(dict.fromkeys(["name", email_field] + [f for _, f in restrictions]))
    records = frappe.get_all(source_doctype, fields=fields)

    for record in records:
        email = record.get(email_field)
        if not email or not frappe.db.exists("User", email):
            continue

        user = frappe.get_doc("User", email)
        if role not in [r.role for r in user.roles]:
            user.append("roles", {"role": role})
            user.save(ignore_permissions=True)

        for allow_doctype, source_fieldname in restrictions:
            party = record.get(source_fieldname)
            if not party:
                continue
            exists = frappe.db.exists("User Permission", {
                "user": email,
                "allow": allow_doctype,
                "for_value": party,
            })
            if not exists:
                frappe.get_doc({
                    "doctype": "User Permission",
                    "user": email,
                    "allow": allow_doctype,
                    "for_value": party,
                }).insert(ignore_permissions=True)
