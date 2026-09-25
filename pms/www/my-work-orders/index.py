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


def _get_own_work_order(work_order):
    supplier = frappe.db.get_value("Supplier", {"email_id": frappe.session.user}, "name")
    if not supplier:
        frappe.throw("No Supplier linked to your account.", frappe.PermissionError)

    doc = frappe.get_doc("Work Order", work_order)
    if doc.vendor != supplier:
        frappe.throw("You can only update Work Orders assigned to you.", frappe.PermissionError)
    return doc


@frappe.whitelist()
def update_actual_cost(work_order, actual_cost):
    """Portal-safe endpoint: a vendor can only update the actual_cost of a
    Work Order assigned to their own Supplier record."""
    doc = _get_own_work_order(work_order)
    doc.actual_cost = actual_cost
    doc.save(ignore_permissions=True)
    return doc.actual_cost


@frappe.whitelist()
def confirm_work_order(work_order):
    """Portal-safe endpoint for a tenant: confirm a fix is done. Ownership
    is verified inside Work Order.confirm_by_tenant() itself."""
    doc = frappe.get_doc("Work Order", work_order)
    doc.confirm_by_tenant()
    return True


@frappe.whitelist()
def upload_completion_photo(work_order, file_url, caption=None):
    """Portal-safe endpoint: a vendor attaches a proof-of-work photo to
    their own Work Order (the file itself is uploaded separately via
    Frappe's standard /api/method/upload_file, then this call records it
    against the document)."""
    doc = _get_own_work_order(work_order)
    doc.append("completion_photos", {"image": file_url, "caption": caption})
    doc.save(ignore_permissions=True)
    return len(doc.completion_photos)
