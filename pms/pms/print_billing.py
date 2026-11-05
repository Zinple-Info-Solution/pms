# Copyright (c) 2026, admin and contributors
"""Data for the PMS Rent Invoice and PMS Payment Receipt print formats: the
company, tenant and lease details that live outside the document itself."""

import frappe
from frappe.contacts.doctype.address.address import get_company_address
from frappe.utils import formatdate


def get_invoice_print_data(doc):
    lease = next((row.custom_lease_agreement for row in doc.items if row.get("custom_lease_agreement")), None)
    return frappe._dict(
        company=_get_company(doc.company),
        tenant=_get_tenant(doc.customer),
        lease=lease,
        property=frappe.db.get_value("Lease Agreement", lease, "building") if lease else None,
        period=_get_billing_period(doc),
    )


def get_payment_print_data(doc):
    references = []
    for row in doc.get("references") or []:
        is_invoice = row.reference_doctype == "Sales Invoice"
        invoice = frappe.get_doc("Sales Invoice", row.reference_name) if is_invoice else None
        references.append(
            frappe._dict(
                row=row,
                period=_get_billing_period(invoice) if invoice else None,
            )
        )
    return frappe._dict(
        company=_get_company(doc.company),
        tenant=_get_tenant(doc.party) if doc.party_type == "Customer" else None,
        references=references,
    )


def _get_company(company):
    details = frappe.db.get_value("Company", company, ["phone_no", "email", "website", "tax_id"], as_dict=True)
    details.name = company
    details.address = get_company_address(company).company_address_display
    return details


def _get_tenant(customer):
    return frappe.db.get_value(
        "Tenant", {"customer": customer}, ["name", "mobile_no", "email", "address"], as_dict=True
    )


def _get_billing_period(invoice):
    """The rent schedule period the invoice bills, else its billing dates."""
    period = frappe.db.get_value("Rent Schedule", {"sales_invoice": invoice.name}, "billing_period")
    if period:
        return period
    start, end = invoice.get("custom_billing_from_date"), invoice.get("custom_billing_to_date")
    if start and end:
        return f"{formatdate(start)} → {formatdate(end)}"
    return None
