# Copyright (c) 2026, admin and contributors
"""WhatsApp notifications via the Meta WhatsApp Cloud API. Off by default
(PMS Integration Settings.whatsapp_enabled) — every call site that uses
this already sends the same notice by email first, so a disabled or
mis-configured WhatsApp integration never blocks anything, it just logs
and the tenant/owner still gets the email."""

import re

import frappe
import requests

GRAPH_API = "https://graph.facebook.com/v19.0"


def is_enabled():
    return bool(frappe.db.get_single_value("PMS Integration Settings", "whatsapp_enabled"))


def send_whatsapp(to_number, message):
    """Best-effort send. Returns True on success, False otherwise (including
    when the integration is off) — callers should not depend on this for
    anything beyond a notification."""
    if not is_enabled():
        return False

    digits = re.sub(r"\D", "", to_number or "")
    if not digits:
        return False

    settings = frappe.get_single("PMS Integration Settings")
    phone_number_id = settings.whatsapp_phone_number_id
    access_token = settings.get_password("whatsapp_access_token", raise_exception=False)
    if not phone_number_id or not access_token:
        frappe.log_error(
            "WhatsApp is enabled but Phone Number ID or Access Token is missing.",
            "WhatsApp send skipped",
        )
        return False

    try:
        response = requests.post(
            f"{GRAPH_API}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": digits,
                "type": "text",
                "text": {"body": message},
            },
            timeout=15,
        )
        response.raise_for_status()
        return True
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"WhatsApp send failed: {to_number}")
        return False
