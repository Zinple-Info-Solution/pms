# Copyright (c) 2026, admin and contributors
import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view your work orders.", frappe.PermissionError)

    supplier = frappe.db.get_value("Supplier", {"email_id": frappe.session.user}, "name")
    if not supplier:
        context.no_supplier = True
        return context

    context.supplier = supplier

    context.work_orders = frappe.get_all(
        "Work Order",
        filters={"vendor": supplier},
        fields=["name", "property", "unit", "priority", "status", "description",
                "estimated_cost", "actual_cost", "purchase_invoice"],
        order_by="modified desc",
        limit_page_length=50,
    )

    return context


@frappe.whitelist()
def update_actual_cost(work_order, actual_cost):
    """Portal-safe endpoint: a vendor can only update the actual_cost of a
    Work Order assigned to their own Supplier record."""
    supplier = frappe.db.get_value("Supplier", {"email_id": frappe.session.user}, "name")
    if not supplier:
        frappe.throw("No Supplier linked to your account.", frappe.PermissionError)

    doc = frappe.get_doc("Work Order", work_order)
    if doc.vendor != supplier:
        frappe.throw("You can only update Work Orders assigned to you.", frappe.PermissionError)

    doc.actual_cost = actual_cost
    doc.save(ignore_permissions=True)
    return doc.actual_cost
