# Copyright (c) 2026, admin and contributors
import frappe

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

    context.statements = frappe.get_all(
        "Owner Statement",
        filters={"owner_id": owner},
        fields=["name", "property", "period_start", "period_end", "gross_income",
                "gross_expense", "management_fee", "net_distributable", "status"],
        order_by="period_start desc",
        limit_page_length=24,
    )

    return context
