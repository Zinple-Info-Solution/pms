# Copyright (c) 2026, admin and contributors
"""Razorpay Payment Links for rent invoices, matching the blueprint's
"Payment gateway / bank feed auto-matched to invoice". Off by default
(PMS Integration Settings.razorpay_enabled) — create_payment_link() just
returns None when disabled/misconfigured, so every caller falls back to
the existing "view and pay on your tenant portal" link.

Uses Razorpay's hosted Payment Links API (POST /v1/payment_links) rather
than embedding Checkout.js, since all we need is a URL to put in an email
or WhatsApp message. reference_id is set to the Sales Invoice name, which
the webhook reads back — no extra field needed on Sales Invoice to map
a payment back to its invoice.
"""

import hashlib
import hmac

import frappe
import requests
from frappe.utils import flt

API_BASE = "https://api.razorpay.com/v1"


def is_enabled():
    return bool(frappe.db.get_single_value("PMS Integration Settings", "razorpay_enabled"))


def _auth():
    settings = frappe.get_single("PMS Integration Settings")
    key_id = settings.razorpay_key_id
    key_secret = settings.get_password("razorpay_key_secret", raise_exception=False)
    if not key_id or not key_secret:
        return None
    return key_id, key_secret


def create_payment_link(sales_invoice):
    """Returns a hosted Razorpay payment link URL for this Sales Invoice
    (a frappe Document or name), or None if disabled, misconfigured, or
    the API call fails — never raises, since this only ever augments an
    email/WhatsApp message that already has a portal link as the fallback."""
    if not is_enabled():
        return None

    auth = _auth()
    if not auth:
        frappe.log_error(
            "Razorpay is enabled but Key ID or Key Secret is missing.",
            "Razorpay payment link skipped",
        )
        return None

    si = sales_invoice if hasattr(sales_invoice, "customer") else frappe.get_doc("Sales Invoice", sales_invoice)
    amount = flt(si.outstanding_amount) or flt(si.grand_total)
    if amount <= 0:
        return None

    email = frappe.db.get_value("Customer", si.customer, "email_id") or frappe.db.get_value(
        "Tenant", {"customer": si.customer}, "email"
    )
    phone = frappe.db.get_value("Tenant", {"customer": si.customer}, "mobile_no")

    try:
        response = requests.post(
            f"{API_BASE}/payment_links",
            auth=auth,
            json={
                "amount": int(round(amount * 100)),
                "currency": si.currency or "INR",
                "description": f"Rent invoice {si.name}",
                "reference_id": si.name,
                "customer": {
                    "name": si.customer_name or si.customer,
                    "email": email or "",
                    "contact": phone or "",
                },
                "notify": {"sms": bool(phone), "email": bool(email)},
                "callback_url": frappe.utils.get_url("/my-lease"),
                "callback_method": "get",
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("short_url")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Razorpay payment link failed: {si.name}")
        return None


def _verify_signature(raw_body, signature, secret):
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook():
    """Razorpay webhook endpoint — point Razorpay's dashboard at
    /api/method/pms.pms.integrations.razorpay_gateway.webhook. On a paid
    payment link, creates a submitted Payment Entry against the Sales
    Invoice named in reference_id, which pms.pms.billing.on_payment_entry
    then uses to flip the matching Rent Schedule row to Paid — the same
    path a manually-entered Payment Entry already takes."""
    settings = frappe.get_single("PMS Integration Settings")
    if not settings.razorpay_enabled:
        frappe.throw("Razorpay integration is disabled", frappe.PermissionError)

    secret = settings.get_password("razorpay_webhook_secret", raise_exception=False)
    raw_body = frappe.request.get_data()
    signature = frappe.request.headers.get("X-Razorpay-Signature")
    if not secret or not _verify_signature(raw_body, signature, secret):
        frappe.throw("Invalid webhook signature", frappe.PermissionError)

    # Signature verified above is the real auth here — elevate from Guest
    # so the Payment Entry creation below doesn't hit permission checks.
    frappe.set_user("Administrator")

    payload = frappe.parse_json(raw_body.decode("utf-8"))
    event = payload.get("event")
    if event not in ("payment_link.paid", "payment.captured"):
        return {"status": "ignored"}

    entity = (
        payload.get("payload", {}).get("payment_link", {}).get("entity")
        or payload.get("payload", {}).get("payment", {}).get("entity")
        or {}
    )
    invoice_name = entity.get("reference_id") or entity.get("notes", {}).get("reference_id")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_payment_id = payment_entity.get("id") or entity.get("id")
    amount_paid = flt(payment_entity.get("amount") or entity.get("amount_paid") or 0) / 100

    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.log_error(f"Razorpay webhook: no matching Sales Invoice for {invoice_name}", "Razorpay webhook")
        return {"status": "no_match"}

    if razorpay_payment_id and frappe.db.exists("Payment Entry", {"reference_no": razorpay_payment_id}):
        return {"status": "already_processed"}

    si = frappe.get_doc("Sales Invoice", invoice_name)
    if si.docstatus != 1 or flt(si.outstanding_amount) <= 0:
        return {"status": "nothing_outstanding"}

    # get_payment_entry() is the same helper ERPNext's own "Make Payment"
    # button on a Sales Invoice uses — it derives paid_from/paid_to and
    # the allocation from the invoice itself, instead of us guessing at
    # the right receivable/bank accounts.
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    pe = get_payment_entry("Sales Invoice", si.name, ignore_permissions=True)
    pe.reference_no = razorpay_payment_id or si.name
    pe.reference_date = frappe.utils.today()
    if frappe.db.exists("Mode of Payment", "Razorpay"):
        pe.mode_of_payment = "Razorpay"
    if amount_paid and amount_paid < flt(si.outstanding_amount):
        pe.paid_amount = amount_paid
        pe.received_amount = amount_paid
        for ref in pe.references:
            if ref.reference_name == si.name:
                ref.allocated_amount = amount_paid
    pe.insert(ignore_permissions=True)
    pe.submit()

    return {"status": "payment_entry_created", "payment_entry": pe.name}
