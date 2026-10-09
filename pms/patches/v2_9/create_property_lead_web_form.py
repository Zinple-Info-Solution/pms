# Copyright (c) 2026, admin and contributors
"""Closes a flowchart gap: "Website enquiry -> Create Lead from web form"
was previously desk-only. Publishes a public (no login required) Web
Form at /enquiry that creates a Property Lead directly, matching the
"no-code Web Form" automation in the flowchart's own automation list.
"""

import frappe

WEB_FORM_NAME = "Property Enquiry"


def execute():
    if not frappe.db.exists("DocType", "Property Lead"):
        return
    # Web Form autonames from a slug of the title, not the title itself
    # (e.g. "Property Enquiry" -> "property-enquiry") — check by doc_type
    # instead of guessing the generated name.
    if frappe.db.exists("Web Form", {"doc_type": "Property Lead"}):
        return

    frappe.get_doc({
        "doctype": "Web Form",
        "title": WEB_FORM_NAME,
        "route": "enquiry",
        "doc_type": "Property Lead",
        "module": "pms",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "allow_multiple": 1,
        "success_message": "Thanks for your interest — a leasing agent will be in touch shortly.",
        "web_form_fields": [
            {"fieldname": "lead_name", "fieldtype": "Data", "label": "Your Name", "reqd": 1},
            {"fieldname": "phone", "fieldtype": "Data", "label": "Phone", "reqd": 1},
            {"fieldname": "email", "fieldtype": "Data", "label": "Email"},
            {"fieldname": "notes", "fieldtype": "Small Text", "label": "Which properties are you interested in, and what are you looking for?"},
        ],
    }).insert(ignore_permissions=True)

    frappe.db.commit()
