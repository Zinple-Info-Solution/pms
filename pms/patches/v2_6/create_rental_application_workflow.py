# Copyright (c) 2026, admin and contributors
"""Phase 7: define the Rental Application Workflow.

Submitted -> Screening -> Approved / Rejected. A second good Workflow
candidate for this rewrite: Leasing Agent creates/submits, Property
Manager screens and makes the approve/reject call — a genuine role-gated
gate before a Lease exists, distinct enough to justify Workflow over a
hardcoded status field.
"""

import frappe

WORKFLOW_NAME = "Rental Application Workflow"
STATES = ["Submitted", "Screening", "Approved", "Rejected"]
ACTIONS = ["Start Screening", "Approve", "Reject"]


def execute():
    if not frappe.db.exists("DocType", "Rental Application"):
        return
    if frappe.db.exists("Workflow", WORKFLOW_NAME):
        return

    for role in ["Leasing Agent", "Property Manager"]:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
                ignore_permissions=True
            )

    for state in STATES:
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
                ignore_permissions=True
            )

    for action in ACTIONS:
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
                ignore_permissions=True
            )

    frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": WORKFLOW_NAME,
        "document_type": "Rental Application",
        "workflow_state_field": "status",
        "is_active": 1,
        "send_email_alert": 0,
        "states": [
            {"state": "Submitted", "doc_status": "0", "allow_edit": "Leasing Agent"},
            {"state": "Screening", "doc_status": "0", "allow_edit": "Property Manager"},
            {"state": "Approved", "doc_status": "0", "allow_edit": "Property Manager"},
            {"state": "Rejected", "doc_status": "0", "allow_edit": "Property Manager"},
        ],
        "transitions": [
            {
                "state": "Submitted", "action": "Start Screening", "next_state": "Screening",
                "allowed": "Property Manager",
            },
            {
                "state": "Screening", "action": "Approve", "next_state": "Approved",
                "allowed": "Property Manager",
            },
            {
                "state": "Screening", "action": "Reject", "next_state": "Rejected",
                "allowed": "Property Manager",
            },
        ],
    }).insert(ignore_permissions=True)

    frappe.db.commit()
