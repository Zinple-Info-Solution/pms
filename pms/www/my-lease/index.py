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
        fields=["name", "subject", "status", "priority", "request_date", "work_order"],
        order_by="request_date desc",
        limit_page_length=10,
    )
    context.maintenance_requests = maintenance_requests

    work_order_names = [m.work_order for m in maintenance_requests if m.work_order]
    context.confirmable_work_orders = []
    if work_order_names:
        context.confirmable_work_orders = frappe.get_all(
            "Work Order",
            filters={"name": ["in", work_order_names], "status": ["in", ["Completed", "Closed"]], "tenant_confirmed": 0},
            pluck="name",
        )

    active_lease_names = [l.name for l in leases if l.status in ("Active", "Notice Given")]
    context.active_units = []
    if active_lease_names:
        context.active_units = frappe.get_all(
            "Lease Agreement Unit",
            filters={"parent": ["in", active_lease_names]},
            fields=["parent AS lease", "unit_id"],
        )

    return context


@frappe.whitelist()
def create_maintenance_request(lease, unit_id, subject, issue_type, priority=None, description=None):
    """Portal-safe endpoint: a tenant can only raise a Maintenance Request
    against a unit on one of their own active leases."""
    tenant = frappe.db.get_value("Tenant", {"email": frappe.session.user}, "name")
    if not tenant:
        frappe.throw("No Tenant record linked to your account.", frappe.PermissionError)

    lease_doc = frappe.db.get_value(
        "Lease Agreement", lease,
        ["tenant", "building", "status", "docstatus"], as_dict=True,
    )
    if (
        not lease_doc
        or lease_doc.tenant != tenant
        or lease_doc.docstatus != 1
        or lease_doc.status not in ("Active", "Notice Given")
    ):
        frappe.throw("You can only raise requests against your own active lease.", frappe.PermissionError)

    on_lease = frappe.db.exists(
        "Lease Agreement Unit", {"parent": lease, "unit_id": unit_id}
    )
    if not on_lease:
        frappe.throw("That unit is not part of the selected lease.", frappe.PermissionError)

    request = frappe.get_doc({
        "doctype": "Maintenance Request",
        "tenant": tenant,
        "building": lease_doc.building,
        "unit": unit_id,
        "request_date": frappe.utils.today(),
        "subject": subject,
        "issue_type": issue_type,
        "priority": priority or "Medium",
        "description": description,
    })
    request.insert(ignore_permissions=True)
    return request.name
