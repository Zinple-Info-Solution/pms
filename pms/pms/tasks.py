# Copyright (c) 2026, admin and contributors
# Scheduled tasks for PMS — wired in hooks.py -> scheduler_events

import frappe
from frappe.utils import today, add_days, date_diff, getdate


def check_lease_expiry():
    """
    Runs daily.
    Finds Active, submitted Lease Agreements whose end_date has passed:
      1. Sets their status to 'Expired'
      2. Releases their Assets back to 'Vacent'
      3. Creates a Notification Log for the lease owner
    """
    expired_leases = frappe.get_all(
        "Lease Agreement",
        filters={
            "status": "Active",
            "docstatus": 1,
            "end_date": ["<", today()],
        },
        fields=["name", "owner", "tenant", "building", "end_date"],
    )

    for lease in expired_leases:
        try:
            doc = frappe.get_doc("Lease Agreement", lease.name)

            # 1. Mark lease Expired
            doc.db_set("status", "Expired")

            # 2. Release assets back to Vacant
            for row in doc.units or []:
                if row.unit_id and frappe.db.exists("Asset", row.unit_id):
                    frappe.db.set_value(
                        "Asset",
                        row.unit_id,
                        {
                            "custom_occupancy_status": "Vacent",
                            "custom_start_date": None,
                            "custom_end_date": None,
                        },
                    )

            # 3. Notify the owner in-app
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Lease {doc.name} has expired",
                "for_user": doc.owner,
                "type": "Alert",
                "document_type": "Lease Agreement",
                "document_name": doc.name,
                "email_content": (
                    f"Lease Agreement <b>{doc.name}</b> "
                    f"(Tenant: {doc.tenant}, Building: {doc.building}) "
                    f"expired on {doc.end_date}. Units have been released."
                ),
            }).insert(ignore_permissions=True)

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"check_lease_expiry failed for {lease.name}",
            )


def send_lease_expiry_reminders(days_before: int = 30):
    """
    Runs daily.
    Sends an in-app notification + email for Active leases
    expiring within `days_before` days.
    """
    upcoming = frappe.get_all(
        "Lease Agreement",
        filters={
            "status": "Active",
            "docstatus": 1,
            "end_date": ["between", [today(), add_days(today(), days_before)]],
        },
        fields=["name", "owner", "tenant", "building", "end_date"],
    )

    for lease in upcoming:
        days_left = date_diff(getdate(lease.end_date), getdate(today()))

        # Only remind at 30, 15, 7, 3, 1 days — not every single day
        if days_left not in (30, 15, 7, 3, 1):
            continue

        try:
            subject = f"Lease {lease.name} expires in {days_left} day(s)"

            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": subject,
                "for_user": lease.owner,
                "type": "Alert",
                "document_type": "Lease Agreement",
                "document_name": lease.name,
                "email_content": (
                    f"Lease Agreement <b>{lease.name}</b> "
                    f"(Tenant: {lease.tenant}, Building: {lease.building}) "
                    f"will expire on <b>{lease.end_date}</b>.<br>"
                    f"Please arrange renewal or termination."
                ),
            }).insert(ignore_permissions=True)

            # Optional email (silently skipped if no outgoing email is set up)
            recipient = frappe.db.get_value("User", lease.owner, "email")
            if recipient:
                frappe.sendmail(
                    recipients=[recipient],
                    subject=subject,
                    message=(
                        f"Lease Agreement {lease.name} for tenant {lease.tenant} "
                        f"in building {lease.building} expires on {lease.end_date} "
                        f"({days_left} days from today)."
                    ),
                    delayed=True,
                )

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"send_lease_expiry_reminders failed for {lease.name}",
            )


def send_overdue_rent_reminders():
    """
    Runs daily. Notifies the lease owner about Pending rent cycles that are
    past their due date — at 1, 3, 7, 14 and 30 days overdue (not every day).
    """
    from frappe.utils import date_diff as _date_diff

    rows = frappe.db.sql("""
        SELECT rs.name, rs.parent AS lease, rs.due_date, rs.total_amount,
               rs.billing_period, la.tenant, la.owner
        FROM `tabRent Schedule` rs
        INNER JOIN `tabLease Agreement` la ON la.name = rs.parent
        WHERE rs.status = 'Pending'
          AND rs.due_date < %s
          AND la.docstatus = 1
          AND la.status = 'Active'
    """, today(), as_dict=True)

    for r in rows:
        overdue_days = _date_diff(getdate(today()), getdate(r.due_date))
        if overdue_days not in (1, 3, 7, 14, 30):
            continue

        try:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": (
                    f"Rent OVERDUE {overdue_days} day(s): "
                    f"lease {r.lease} ({r.billing_period})"
                ),
                "for_user": r.owner,
                "type": "Alert",
                "document_type": "Lease Agreement",
                "document_name": r.lease,
                "email_content": (
                    f"Rent for lease <b>{r.lease}</b> (Tenant: {r.tenant}) "
                    f"period <b>{r.billing_period}</b> was due on "
                    f"<b>{r.due_date}</b> and is still pending. "
                    f"Amount: {frappe.format_value(r.total_amount, {'fieldtype': 'Currency'})}"
                ),
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Overdue rent reminder failed: {r.lease}",
            )
