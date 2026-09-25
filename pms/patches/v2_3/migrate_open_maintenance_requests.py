# Copyright (c) 2026, admin and contributors
"""Phase 4: back-fill a Work Order for every currently Open / In Progress /
On Hold Maintenance Request, so the new Work Order lifecycle picks up
in-flight requests rather than only new ones. Resolved/Closed requests are
left as history only. "On Hold" has no exact equivalent workflow state, so
it maps to "Assigned" — flagged here for manual review since that mapping
is a judgment call, not a mechanical one.

Idempotent via the existing `work_order` link check.
"""

import frappe

STARTING_STATE = {
    "Open": "Open",
    "In Progress": "In Progress",
    "On Hold": "Assigned",
}


def execute():
    if not frappe.db.exists("DocType", "Work Order"):
        return

    requests = frappe.get_all(
        "Maintenance Request",
        filters={"status": ["in", list(STARTING_STATE.keys())], "work_order": ["in", ["", None]]},
        fields=["name", "building", "unit", "priority", "subject", "description", "assigned_to", "status"],
    )
    if not requests:
        return

    on_hold_mapped = []

    for r in requests:
        work_order = frappe.get_doc({
            "doctype": "Work Order",
            "maintenance_request": r.name,
            "property": r.building,
            "unit": r.unit,
            "priority": r.priority,
            "description": f"{r.subject}\n\n{r.description or ''}".strip(),
            "assigned_to": r.assigned_to,
            "status": STARTING_STATE[r.status],
        })
        work_order.insert(ignore_permissions=True)
        frappe.db.set_value("Maintenance Request", r.name, "work_order", work_order.name)

        if r.status == "On Hold":
            on_hold_mapped.append(f"{r.name} -> {work_order.name}")

    frappe.db.commit()

    frappe.log_error(
        title="PMS Work Order Migration",
        message=f"{len(requests)} Work Order(s) created from open Maintenance Requests.",
    )
    if on_hold_mapped:
        frappe.log_error(
            title="PMS Work Order Migration: On Hold mapping",
            message=(
                "The following 'On Hold' requests were mapped to the 'Assigned' "
                "starting state (no exact equivalent) — review manually:\n"
                + "\n".join(on_hold_mapped)
            ),
        )
