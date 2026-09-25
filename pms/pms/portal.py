# Copyright (c) 2026, admin and contributors
# Portal user provisioning — shared by the one-time backfill patch
# (pms.patches.v2_7.create_portal_roles_and_permissions) and the
# per-event triggers below (e.g. sending a portal login on Move In).

import frappe


def invite_tenant_to_portal(tenant_name):
    """Send a Frappe portal invite to a Tenant's email and wire the Tenant/
    Customer User Permission restrictions once they have an account.
    Safe to call repeatedly — does nothing if already invited/wired."""
    tenant = frappe.get_doc("Tenant", tenant_name)
    if not tenant.email:
        return

    if not frappe.db.exists("User", tenant.email):
        try:
            frappe.get_doc({
                "doctype": "User",
                "email": tenant.email,
                "first_name": tenant.full_name,
                "user_type": "Website User",
                "send_welcome_email": 1,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Portal invite failed: {tenant_name}")
            return

    user = frappe.get_doc("User", tenant.email)
    if "Tenant" not in [r.role for r in user.roles]:
        user.append("roles", {"role": "Tenant"})
        user.save(ignore_permissions=True)

    for allow_doctype, value in [("Customer", tenant.customer), ("Tenant", tenant.name)]:
        if value and not frappe.db.exists("User Permission", {
            "user": tenant.email, "allow": allow_doctype, "for_value": value,
        }):
            frappe.get_doc({
                "doctype": "User Permission", "user": tenant.email,
                "allow": allow_doctype, "for_value": value,
            }).insert(ignore_permissions=True)
