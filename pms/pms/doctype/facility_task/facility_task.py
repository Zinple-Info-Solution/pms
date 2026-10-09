# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, getdate, today

FREQUENCY_DAYS = {"Daily": 1, "Weekly": 7}


class FacilityTask(Document):

    @frappe.whitelist()
    def mark_completed(self, notes=None):
        """Log a completion and roll next_due_date forward by one cycle."""
        log = frappe.get_doc({
            "doctype": "Facility Task Log",
            "task": self.name,
            "completion_date": today(),
            "completed_by": frappe.session.user,
            "notes": notes,
        })
        log.insert(ignore_permissions=True)

        self.db_set("last_completed_date", today())
        self.db_set("next_due_date", self._next_due_date())
        return log.name

    def _next_due_date(self):
        if self.frequency == "Monthly":
            return add_months(getdate(today()), 1)
        return add_days(getdate(today()), FREQUENCY_DAYS.get(self.frequency, 1))
