# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.workflow import apply_workflow

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view your properties.", frappe.PermissionError)

    owner = frappe.db.get_value("Owner", {"email": frappe.session.user}, "name")
    if not owner:
        context.no_owner = True
        return context

    context.owner = frappe.get_doc("Owner", owner)

    properties = frappe.get_all(
        "Property Owner",
        filters={"owner_id": owner, "parenttype": "Property"},
        fields=["parent AS property", "share_percent"],
    )
    context.properties = properties
    property_names = [p.property for p in properties]

    context.statements = frappe.get_all(
        "Owner Statement",
        filters={"owner_id": owner},
        fields=["name", "property", "period_start", "period_end", "gross_income",
                "gross_expense", "management_fee", "net_distributable", "status"],
        order_by="period_start desc",
        limit_page_length=24,
    )

    context.pending_approvals = []
    if property_names:
        context.pending_approvals = frappe.get_all(
            "Work Order",
            filters={"property": ["in", property_names], "status": "Awaiting Owner Approval"},
            fields=["name", "property", "unit", "description", "estimated_cost", "priority"],
        )

    return context


@frappe.whitelist()
def approve_work_order(work_order):
    """Portal-safe endpoint: an owner can only approve a Work Order on a
    property they actually own."""
    owner = frappe.db.get_value("Owner", {"email": frappe.session.user}, "name")
    if not owner:
        frappe.throw("No Owner record linked to your account.", frappe.PermissionError)

    doc = frappe.get_doc("Work Order", work_order)
    owns_property = frappe.db.exists("Property Owner", {
        "parenttype": "Property", "parent": doc.property, "owner_id": owner,
    })
    if not owns_property:
        frappe.throw("You can only approve work orders on properties you own.", frappe.PermissionError)

    apply_workflow(doc, "Approve")
    return doc.status
