# Copyright (c) 2026, admin and contributors
"""E-signature via Zoho Sign. Off by default
(PMS Integration Settings.esign_enabled) — send_for_esign() just returns
False when disabled or misconfigured, leaving the existing draft-lease +
"unsigned 2+ days" reminder flow as the fallback, same as today.
"""

import hmac

import frappe
import requests

API_BASE = "https://sign.zoho.com/api/v1"


def is_enabled():
    return bool(frappe.db.get_single_value("PMS Integration Settings", "esign_enabled"))


def send_for_esign(lease):
    """lease: a Lease Agreement Document or name. Renders the lease as a
    PDF and creates a Zoho Sign request for the tenant to sign. Returns
    True on success; on any failure, logs and sets esign_status to Failed
    rather than raising — this is called right after a draft lease is
    created and must never block that."""
    if not is_enabled():
        return False

    settings = frappe.get_single("PMS Integration Settings")
    access_token = settings.get_password("zoho_sign_access_token", raise_exception=False)
    if not settings.zoho_sign_account_id or not access_token:
        frappe.log_error(
            "Zoho Sign is enabled but Account ID or Access Token is missing.",
            "E-sign send skipped",
        )
        return False

    doc = lease if hasattr(lease, "tenant") else frappe.get_doc("Lease Agreement", lease)
    tenant_email, tenant_name = frappe.db.get_value(
        "Tenant", doc.tenant, ["email", "full_name"]
    ) or (None, None)
    if not tenant_email:
        frappe.log_error(
            f"Lease {doc.name}: tenant has no email on file, cannot send for e-sign.",
            "E-sign send skipped",
        )
        return False

    try:
        pdf_bytes = frappe.get_print("Lease Agreement", doc.name, as_pdf=True)
        request_config = {
            "requests": {
                "request_name": f"Lease Agreement {doc.name}",
                "actions": [{
                    "action_type": "SIGN",
                    "recipient_name": tenant_name or doc.tenant,
                    "recipient_email": tenant_email,
                    "signing_order": 0,
                    "verify_recipient": False,
                }],
            }
        }
        response = requests.post(
            f"{API_BASE}/requests",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            files={"file": (f"{doc.name}.pdf", pdf_bytes, "application/pdf")},
            data={"data": frappe.as_json(request_config)},
            timeout=30,
        )
        response.raise_for_status()
        request_id = response.json().get("requests", {}).get("request_id")

        doc.db_set("esign_status", "Sent")
        doc.db_set("esign_request_id", request_id)
        return True
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"E-sign send failed: {doc.name}")
        doc.db_set("esign_status", "Failed")
        return False


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook():
    """Zoho Sign webhook endpoint — point Zoho Sign's webhook config at
    /api/method/pms.pms.integrations.esign.webhook with a custom header
    X-PMS-Webhook-Secret set to PMS Integration Settings.zoho_sign_webhook_secret.
    (Zoho Sign's own request-signing scheme isn't assumed here, since this
    was built without a live account to verify it against — a shared
    secret header is the most provider-agnostic way to authenticate this,
    and Zoho Sign's webhook config supports adding custom headers.)

    On a completed signing request, submits the matching Lease Agreement
    — the same effect as a staff member submitting it manually once a
    tenant signs on paper."""
    settings = frappe.get_single("PMS Integration Settings")
    if not settings.esign_enabled:
        frappe.throw("E-sign integration is disabled", frappe.PermissionError)

    secret = settings.get_password("zoho_sign_webhook_secret", raise_exception=False)
    provided = frappe.get_request_header("X-PMS-Webhook-Secret")
    if not secret or not provided or not hmac.compare_digest(secret, provided):
        frappe.throw("Invalid webhook secret", frappe.PermissionError)

    frappe.set_user("Administrator")

    payload = frappe.parse_json(frappe.request.get_data().decode("utf-8"))
    requests_info = payload.get("requests", {})
    request_id = requests_info.get("request_id")
    request_status = (requests_info.get("request_status") or "").lower()
    if not request_id:
        return {"status": "ignored"}

    lease_name = frappe.db.get_value(
        "Lease Agreement", {"esign_request_id": request_id}, "name"
    )
    if not lease_name:
        frappe.log_error(
            f"E-sign webhook: no Lease Agreement for request {request_id}", "E-sign webhook"
        )
        return {"status": "no_match"}

    if request_status not in ("completed", "signed"):
        return {"status": "noted", "request_status": request_status}

    lease = frappe.get_doc("Lease Agreement", lease_name)
    lease.db_set("esign_status", "Signed")
    if lease.docstatus == 0:
        lease.submit()

    return {"status": "lease_submitted", "lease": lease_name}
