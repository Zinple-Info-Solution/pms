# Copyright (c) 2026, admin and contributors
"""Closes a flowchart gap: "Lead created -> Assign to agent (round-robin)".
Only creates the Assignment Rule if at least one User already holds the
Leasing Agent role — an empty round-robin pool isn't useful and would
just silently never assign anything, so this is skipped (not failed)
until real agent users exist. Re-run this patch (or configure it by
hand from Settings > Assignment Rule) after adding agents.
"""

import frappe

RULE_NAME = "PMS Lead Round Robin"


def execute():
    if not frappe.db.exists("DocType", "Property Lead"):
        return
    if frappe.db.exists("Assignment Rule", RULE_NAME):
        return

    agents = frappe.get_all(
        "Has Role", filters={"role": "Leasing Agent", "parenttype": "User"}, pluck="parent"
    )
    active_agents = frappe.get_all(
        "User", filters={"name": ["in", agents], "enabled": 1}, pluck="name"
    )
    if not active_agents:
        return

    frappe.get_doc({
        "doctype": "Assignment Rule",
        "name": RULE_NAME,
        "document_type": "Property Lead",
        "rule": "Round Robin",
        "disabled": 0,
        "priority": 0,
        "assign_condition": "status == \"New\"",
        "due_date_based_on": "",
        "users": [{"user": u} for u in active_agents],
    }).insert(ignore_permissions=True)
    frappe.db.commit()
