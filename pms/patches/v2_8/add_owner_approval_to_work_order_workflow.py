# Copyright (c) 2026, admin and contributors
"""Closes a real gap against the property-management flowchart: the
owner should be able to approve a maintenance job over their own
approval limit from their own portal, not only via Property Manager/
Accountant on the desk. The Work Order Workflow already exists on sites
that ran the Phase 4 patch, so add the missing Owner transition here
rather than relying on that patch's idempotency check (which now skips
re-running it). Safe to re-run.
"""

import frappe

WORKFLOW_NAME = "Work Order Workflow"


def execute():
    if not frappe.db.exists("Workflow", WORKFLOW_NAME):
        return

    if not frappe.db.exists("Role", "Owner"):
        frappe.get_doc({"doctype": "Role", "role_name": "Owner", "desk_access": 0}).insert(
            ignore_permissions=True
        )

    workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
    already_has_it = any(
        t.state == "Awaiting Owner Approval" and t.action == "Approve" and t.allowed == "Owner"
        for t in workflow.transitions
    )
    if already_has_it:
        return

    workflow.append("transitions", {
        "state": "Awaiting Owner Approval",
        "action": "Approve",
        "next_state": "In Progress",
        "allowed": "Owner",
    })
    workflow.save(ignore_permissions=True)
    frappe.db.commit()
