# Copyright (c) 2026, admin and contributors
# Scheduled tasks for PMS — wired in hooks.py -> scheduler_events

import frappe
from frappe.utils import today, add_days, date_diff, getdate
from pms.pms.doctype.lease_agreement.lease_agreement import log_occupancy_event
from pms.pms.doctype.unit.unit import sync_unit_listing
from pms.pms.integrations.whatsapp import send_whatsapp
from pms.pms.integrations.razorpay_gateway import create_payment_link


def _get_property_managers():
    """Users to notify about lease-level events. `Lease Agreement.owner` is
    Frappe's own record-creator metadata field, not a real "who manages this
    lease" field (leases created via a migration/patch all have the same
    creator) — so lease-level reminders go to everyone holding the Property
    Manager role instead, falling back to Administrator if none exist yet
    (same fallback pattern as the Lead round-robin Assignment Rule patch)."""
    managers = frappe.get_all(
        "Has Role", filters={"role": "Property Manager", "parenttype": "User"}, pluck="parent"
    )
    active = frappe.get_all("User", filters={"name": ["in", managers], "enabled": 1}, pluck="name")
    return active or ["Administrator"]


def _notify_property_managers(subject, document_type, document_name, email_content=None, send_email=False):
    for user in _get_property_managers():
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": subject,
            "for_user": user,
            "type": "Alert",
            "document_type": document_type,
            "document_name": document_name,
            "email_content": email_content,
        }).insert(ignore_permissions=True)
        if send_email:
            email = frappe.db.get_value("User", user, "email")
            if email:
                frappe.sendmail(
                    recipients=[email], subject=subject, message=email_content or subject, delayed=True
                )


def check_lease_expiry():
    """
    Runs daily.
    Finds Active, submitted Lease Agreements whose end_date has passed:
      1. Sets their status to 'Expired'
      2. Releases their Units back to 'Vacant'
      3. Creates a Notification Log for the lease owner
    """
    expired_leases = frappe.get_all(
        "Lease Agreement",
        filters={
            "status": "Active",
            "docstatus": 1,
            "end_date": ["<", today()],
        },
        fields=["name", "tenant", "building", "end_date"],
    )

    for lease in expired_leases:
        try:
            doc = frappe.get_doc("Lease Agreement", lease.name)

            # 1. Mark lease Expired
            doc.db_set("status", "Expired")

            # 2. Release units back to Vacant
            for row in doc.units or []:
                if row.unit_id and frappe.db.exists("Unit", row.unit_id):
                    frappe.db.set_value(
                        "Unit",
                        row.unit_id,
                        {
                            "status": "Vacant",
                            "current_occupant_start_date": None,
                            "current_occupant_end_date": None,
                        },
                    )
                    sync_unit_listing(row.unit_id, "Vacant")
                    log_occupancy_event(row.unit_id, "Vacated", lease=doc.name)

            # 3. Notify the property manager(s) in-app
            _notify_property_managers(
                subject=f"Lease {doc.name} has expired",
                document_type="Lease Agreement",
                document_name=doc.name,
                email_content=(
                    f"Lease Agreement <b>{doc.name}</b> "
                    f"(Tenant: {doc.tenant}, Building: {doc.building}) "
                    f"expired on {doc.end_date}. Units have been released."
                ),
            )

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
        fields=["name", "tenant", "building", "end_date"],
    )

    for lease in upcoming:
        days_left = date_diff(getdate(lease.end_date), getdate(today()))

        # Only remind at 30, 15, 7, 3, 1 days — not every single day
        if days_left not in (30, 15, 7, 3, 1):
            continue

        try:
            subject = f"Lease {lease.name} expires in {days_left} day(s)"

            _notify_property_managers(
                subject=subject,
                document_type="Lease Agreement",
                document_name=lease.name,
                email_content=(
                    f"Lease Agreement <b>{lease.name}</b> "
                    f"(Tenant: {lease.tenant}, Building: {lease.building}) "
                    f"will expire on <b>{lease.end_date}</b>.<br>"
                    f"Please arrange renewal or termination."
                ),
                send_email=True,
            )

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"send_lease_expiry_reminders failed for {lease.name}",
            )


def apply_rent_escalations():
    """Runs daily. Applies any due, not-yet-applied Rent Escalation Schedule
    row on Active submitted leases."""
    rows = frappe.db.sql("""
        SELECT res.parent AS lease, res.name AS row_name
        FROM `tabRent Escalation Schedule` res
        INNER JOIN `tabLease Agreement` la ON la.name = res.parent
        WHERE res.applied = 0
          AND res.escalation_date <= %s
          AND la.docstatus = 1
          AND la.status = 'Active'
    """, today(), as_dict=True)

    for r in rows:
        try:
            lease = frappe.get_doc("Lease Agreement", r.lease)
            row = next(x for x in lease.rent_escalation if x.name == r.row_name)
            lease.apply_rent_escalation(row)

            _notify_property_managers(
                subject=f"Rent escalation applied on lease {lease.name}",
                document_type="Lease Agreement",
                document_name=lease.name,
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Rent escalation failed: lease {r.lease}",
            )


def send_overdue_rent_reminders():
    """
    Runs daily. Notifies the lease owner about Pending rent cycles that are
    past their due date — at 1, 3, 7, 14 and 30 days overdue (not every day).
    """
    from frappe.utils import date_diff as _date_diff

    rows = frappe.db.sql("""
        SELECT rs.name, rs.parent AS lease, rs.due_date, rs.total_amount,
               rs.billing_period, rs.sales_invoice, la.tenant, la.customer
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

        amount_fmt = frappe.format_value(r.total_amount, {"fieldtype": "Currency"})

        try:
            _notify_property_managers(
                subject=(
                    f"Rent OVERDUE {overdue_days} day(s): "
                    f"lease {r.lease} ({r.billing_period})"
                ),
                document_type="Lease Agreement",
                document_name=r.lease,
                email_content=(
                    f"Rent for lease <b>{r.lease}</b> (Tenant: {r.tenant}) "
                    f"period <b>{r.billing_period}</b> was due on "
                    f"<b>{r.due_date}</b> and is still pending. "
                    f"Amount: {amount_fmt}"
                ),
            )

            # Nudge the tenant too — day 1/3/7 is meant for them, not just
            # the property manager (who only needs to act at 30 days).
            if overdue_days in (1, 3, 7) and r.sales_invoice:
                pay_url = (
                    create_payment_link(r.sales_invoice)
                    or frappe.utils.get_url("/my-lease")
                )
                tenant_email, tenant_mobile = frappe.db.get_value(
                    "Tenant", r.tenant, ["email", "mobile_no"]
                ) or (None, None)
                reminder_text = (
                    f"Rent of {amount_fmt} for {r.billing_period} was due on "
                    f"{r.due_date} and is still unpaid."
                )
                if tenant_email:
                    frappe.sendmail(
                        recipients=[tenant_email],
                        subject=f"Rent reminder: {amount_fmt} overdue",
                        message=f"<p>{reminder_text}</p><p><a href='{pay_url}'>Pay now</a></p>",
                        delayed=True,
                    )
                if tenant_mobile:
                    send_whatsapp(tenant_mobile, f"{reminder_text} Pay here: {pay_url}")
            # After a few unpaid reminders (7+ days overdue), also raise a
            # formal Delinquency Notice — deduped per lease/due_date/day count.
            if overdue_days >= 7 and not frappe.db.exists("Delinquency Notice", {
                "lease": r.lease, "due_date": r.due_date, "days_overdue": overdue_days,
            }):
                frappe.get_doc({
                    "doctype": "Delinquency Notice",
                    "lease": r.lease,
                    "due_date": r.due_date,
                    "billing_period": r.billing_period,
                    "amount": r.total_amount,
                    "days_overdue": overdue_days,
                    "notice_text": (
                        f"Rent of {frappe.format_value(r.total_amount, {'fieldtype': 'Currency'})} "
                        f"for period {r.billing_period} was due on {r.due_date} and remains unpaid "
                        f"{overdue_days} day(s) later."
                    ),
                }).insert(ignore_permissions=True)

            # At 30 days overdue, open an actual actionable task for the
            # manager (call, payment plan or legal notice) rather than just
            # another notification.
            if overdue_days == 30 and not frappe.db.exists("ToDo", {
                "reference_type": "Lease Agreement", "reference_name": r.lease,
                "description": ["like", "%30+ days overdue%"],
            }):
                frappe.get_doc({
                    "doctype": "ToDo",
                    "description": (
                        f"Lease {r.lease} ({r.tenant}) is 30+ days overdue on "
                        f"{r.billing_period} — call the tenant, arrange a payment "
                        f"plan, or start a legal notice."
                    ),
                    "reference_type": "Lease Agreement",
                    "reference_name": r.lease,
                    "assigned_by": "Administrator",
                    "allocated_to": _get_property_managers()[0],
                    "priority": "High",
                }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Overdue rent reminder failed: {r.lease}",
            )


def send_signature_reminders():
    """Runs daily: nudge about draft leases (generated from an approved
    Rental Application but not yet submitted) that have sat unsigned for
    2+ days. There's no e-sign integration here, so "signed" means
    "submitted" — this reminds whoever needs to chase the paperwork."""
    drafts = frappe.get_all(
        "Lease Agreement",
        filters={"docstatus": 0, "creation": ["<=", add_days(today(), -2)]},
        fields=["name", "tenant", "creation"],
    )
    for lease in drafts:
        try:
            _notify_property_managers(
                subject=f"Lease {lease.name} is still unsigned",
                document_type="Lease Agreement",
                document_name=lease.name,
                email_content=(
                    f"Lease Agreement <b>{lease.name}</b> for tenant "
                    f"<b>{lease.tenant}</b> has been in Draft for "
                    f"{date_diff(getdate(today()), getdate(lease.creation))} day(s). "
                    f"Follow up to get it signed and submitted."
                ),
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Signature reminder failed: {lease.name}")


def send_renewal_offers():
    """Runs daily: 60 days before an Active lease ends, auto-draft a
    renewal (at the current rent — the Property Manager adjusts for any
    increase before sending) and email the tenant. Only offered once per
    lease, tracked via the renewal_offered flag."""
    from pms.pms.doctype.lease_agreement.lease_agreement import make_renewal

    upcoming = frappe.get_all(
        "Lease Agreement",
        filters={
            "status": "Active",
            "docstatus": 1,
            "renewal_offered": 0,
            "end_date": ["between", [today(), add_days(today(), 60)]],
        },
        fields=["name", "tenant"],
    )

    for lease in upcoming:
        try:
            renewal_name = make_renewal(lease.name)
            frappe.db.set_value("Lease Agreement", lease.name, "renewal_offered", 1)

            tenant_email = frappe.db.get_value("Tenant", lease.tenant, "email")
            if tenant_email:
                frappe.sendmail(
                    recipients=[tenant_email],
                    subject=f"Your lease is coming up for renewal",
                    message=(
                        f"<p>Your lease <b>{lease.name}</b> is ending soon. A renewal "
                        f"offer <b>{renewal_name}</b> has been prepared — log in to your "
                        f"tenant portal or contact us to accept it, or let us know if "
                        f"you'll be moving out.</p>"
                    ),
                    delayed=True,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Renewal offer failed: {lease.name}")
