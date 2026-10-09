# Copyright (c) 2026, admin and contributors
# Facility Ops: Cleaning / Security Patrol / Waste Collection reminders.

import frappe
from frappe.utils import today

from pms.pms.tasks import _notify_property_managers


def send_facility_task_reminders():
    """Runs daily: nudge about active Facility Tasks whose next_due_date
    has arrived — notifies the assigned staff/vendor contact if there's a
    linked User, else falls back to the property managers."""
    due = frappe.get_all(
        "Facility Task",
        filters={"is_active": 1, "next_due_date": ["<=", today()]},
        fields=["name", "task_type", "property", "area", "assigned_to"],
    )

    for task in due:
        try:
            subject = f"{task.task_type} due: {task.name}" + (f" ({task.area})" if task.area else "")
            email_content = (
                f"Facility Task <b>{task.name}</b> ({task.task_type}) at "
                f"{task.area or task.property} is due today or overdue."
            )
            if task.assigned_to:
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": subject,
                    "for_user": task.assigned_to,
                    "type": "Alert",
                    "document_type": "Facility Task",
                    "document_name": task.name,
                    "email_content": email_content,
                }).insert(ignore_permissions=True)
            else:
                _notify_property_managers(
                    subject=subject,
                    document_type="Facility Task",
                    document_name=task.name,
                    email_content=email_content,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Facility task reminder failed: {task.name}")
