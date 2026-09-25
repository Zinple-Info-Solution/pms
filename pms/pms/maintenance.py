# Copyright (c) 2026, admin and contributors
# Preventive maintenance scheduling.

import frappe
from frappe.utils import getdate, today, add_days, add_months

FREQUENCY_MONTHS = {
    "Weekly": None,   # handled via add_days(7) below
    "Monthly": 1,
    "Quarterly": 3,
    "Half-Yearly": 6,
    "Yearly": 12,
}


def generate_preventive_work_orders():
    """Runs daily: for every active Preventive Maintenance Schedule whose
    next_due_date has arrived, create a Work Order and roll the schedule
    forward to its next occurrence. Idempotent per due date via a direct
    date-forward roll (a schedule can't be "due" twice for the same date
    once next_due_date has moved past it)."""
    due = frappe.get_all(
        "Preventive Maintenance Schedule",
        filters={"is_active": 1, "next_due_date": ["<=", today()]},
        fields=["name", "task_name", "property", "unit", "frequency", "assigned_to"],
    )

    for row in due:
        try:
            work_order = frappe.get_doc({
                "doctype": "Work Order",
                "property": row.property,
                "unit": row.unit,
                "priority": "Low",
                "description": f"Preventive maintenance: {row.task_name}",
                "assigned_to": row.assigned_to,
            })
            work_order.insert(ignore_permissions=True)

            schedule = frappe.get_doc("Preventive Maintenance Schedule", row.name)
            schedule.db_set("last_completed_date", today())
            schedule.db_set("next_due_date", _next_due_date(row.frequency))
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Preventive maintenance Work Order creation failed: {row.name}",
            )


def _next_due_date(frequency):
    if frequency == "Weekly":
        return add_days(getdate(today()), 7)
    months = FREQUENCY_MONTHS.get(frequency, 1)
    return add_months(getdate(today()), months)


def escalate_overdue_work_orders():
    """Runs hourly: flag any Work Order past its SLA due time (and not yet
    Completed/Closed) as breached, and notify the Property Manager once
    per breach."""
    overdue = frappe.get_all(
        "Work Order",
        filters={
            "sla_due_by": ["<", frappe.utils.now_datetime()],
            "sla_breached": 0,
            "status": ["not in", ["Completed", "Closed"]],
        },
        fields=["name", "property", "priority", "description"],
    )

    for wo in overdue:
        try:
            frappe.db.set_value("Work Order", wo.name, "sla_breached", 1)
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"SLA missed: Work Order {wo.name} ({wo.priority})",
                "for_user": frappe.db.get_value(
                    "Property", wo.property, "owner"
                ) or "Administrator",
                "type": "Alert",
                "document_type": "Work Order",
                "document_name": wo.name,
                "email_content": (
                    f"Work Order <b>{wo.name}</b> ({wo.priority} priority) has "
                    f"missed its SLA and is still open: {wo.description or ''}"
                ),
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"SLA escalation failed: {wo.name}")
