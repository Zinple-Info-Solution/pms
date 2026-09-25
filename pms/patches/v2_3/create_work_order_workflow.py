# Copyright (c) 2026, admin and contributors
"""Phase 4: define the Work Order Workflow.

Open -> Assigned -> (conditionally) Awaiting Owner Approval -> In Progress
-> Completed -> Closed. The conditional branch is driven by
Work Order.approval_required (computed in work_order.py's validate(),
comparing estimated_cost against the Property's Maintenance Approval
Limit), so the Workflow's own transition conditions stay simple, safe
`doc.approval_required == ...` expressions rather than live DB lookups.

This is the one genuinely-justified use of Frappe Workflow in this
rewrite: Maintenance Staff and Property Manager/Accountant gate different
transitions, which is exactly what Workflow's role-gated actions are for.
Created via the API (not a static fixture) so validation catches any
structural mistakes; idempotent via existence check.
"""

import frappe

WORKFLOW_NAME = "Work Order Workflow"
STATES = ["Open", "Assigned", "Awaiting Owner Approval", "In Progress", "Completed", "Closed"]
ACTIONS = ["Assign", "Send for Approval", "Start Work", "Approve", "Mark Complete", "Close"]


def execute():
    if not frappe.db.exists("DocType", "Work Order"):
        return
    if frappe.db.exists("Workflow", WORKFLOW_NAME):
        return

    for role in ["Maintenance Staff", "Property Manager", "Accountant"]:
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
        "document_type": "Work Order",
        "workflow_state_field": "status",
        "is_active": 1,
        "send_email_alert": 0,
        "states": [
            {"state": "Open", "doc_status": "0", "allow_edit": "Maintenance Staff"},
            {"state": "Assigned", "doc_status": "0", "allow_edit": "Maintenance Staff"},
            {"state": "Awaiting Owner Approval", "doc_status": "0", "allow_edit": "Property Manager"},
            {"state": "In Progress", "doc_status": "0", "allow_edit": "Maintenance Staff"},
            {"state": "Completed", "doc_status": "0", "allow_edit": "Maintenance Staff"},
            {"state": "Closed", "doc_status": "0", "allow_edit": "Property Manager"},
        ],
        "transitions": [
            {
                "state": "Open", "action": "Assign", "next_state": "Assigned",
                "allowed": "Maintenance Staff",
            },
            {
                "state": "Open", "action": "Assign", "next_state": "Assigned",
                "allowed": "Property Manager",
            },
            {
                "state": "Assigned", "action": "Send for Approval", "next_state": "Awaiting Owner Approval",
                "allowed": "Maintenance Staff", "condition": "doc.approval_required == 1",
            },
            {
                "state": "Assigned", "action": "Start Work", "next_state": "In Progress",
                "allowed": "Maintenance Staff", "condition": "doc.approval_required == 0",
            },
            {
                "state": "Awaiting Owner Approval", "action": "Approve", "next_state": "In Progress",
                "allowed": "Property Manager",
            },
            {
                "state": "Awaiting Owner Approval", "action": "Approve", "next_state": "In Progress",
                "allowed": "Accountant",
            },
            {
                "state": "In Progress", "action": "Mark Complete", "next_state": "Completed",
                "allowed": "Maintenance Staff",
            },
            {
                "state": "Completed", "action": "Close", "next_state": "Closed",
                "allowed": "Property Manager",
            },
        ],
    }).insert(ignore_permissions=True)

    frappe.db.commit()
