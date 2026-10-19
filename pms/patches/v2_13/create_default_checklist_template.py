# Copyright (c) 2026, admin and contributors
"""Move In / Move Out can fill their condition checklist from an Inspection
Template. Give sites with no template a standard one to start from."""

import frappe

TEMPLATE = "Standard Move-In Checklist"
ITEMS = [
    ("Main Door & Locks", "Entrance"),
    ("Keys & Access Cards", "Entrance"),
    ("Walls & Paint", "Living Area"),
    ("Flooring", "Living Area"),
    ("Windows & Grills", "Living Area"),
    ("Lights & Fans", "Electrical"),
    ("Switches & Sockets", "Electrical"),
    ("Kitchen Counter & Sink", "Kitchen"),
    ("Kitchen Cabinets", "Kitchen"),
    ("Bathroom Fittings", "Bathroom"),
    ("Taps & Plumbing", "Bathroom"),
    ("Bedroom Wardrobes", "Bedroom"),
    ("Balcony", "Outdoor"),
]


def execute():
    if frappe.db.count("Inspection Template"):
        return
    frappe.get_doc({
        "doctype": "Inspection Template",
        "template_name": TEMPLATE,
        "items": [{"item_name": name, "category": category} for name, category in ITEMS],
    }).insert(ignore_permissions=True)
