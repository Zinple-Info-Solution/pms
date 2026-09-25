# Copyright (c) 2026, admin and contributors
import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view your lease.", frappe.PermissionError)

    tenant = frappe.db.get_value("Tenant", {"email": frappe.session.user}, "name")
    if not tenant:
        context.no_tenant = True
        return context

    tenant_doc = frappe.get_doc("Tenant", tenant)
    context.tenant = tenant_doc

    leases = frappe.get_all(
        "Lease Agreement",
        filters={"tenant": tenant, "docstatus": 1},
        fields=["name", "building", "start_date", "end_date", "status", "rent_amount", "net_monthly_amount"],
        order_by="start_date desc",
    )
    context.leases = leases

    lease_names = [l.name for l in leases]
    context.rent_schedule = []
    if lease_names:
        context.rent_schedule = frappe.get_all(
            "Rent Schedule",
            filters={"parent": ["in", lease_names]},
            fields=["parent", "due_date", "billing_period", "total_amount", "status", "sales_invoice"],
            order_by="due_date desc",
            limit_page_length=24,
        )

    maintenance_requests = frappe.get_all(
        "Maintenance Request",
        filters={"tenant": tenant},
        fields=["name", "subject", "status", "priority", "request_date"],
        order_by="request_date desc",
        limit_page_length=10,
    )
    context.maintenance_requests = maintenance_requests

    return context
