# Copyright (c) 2026, admin and contributors
"""Property Lead's "Interested Property" became a multi-select
(interested_property Link -> interested_properties Table MultiSelect), so a
lead can show interest in more than one property.

Two cleanups, both only relevant on sites where the old field/web form
already existed before this change:
1. Backfill any existing Property Lead's old interested_property value into
   the new child table. Read via raw SQL, not the ORM, since by the time
   this (post_model_sync) patch runs, interested_property is no longer a
   field Frappe's doctype meta knows about -- but Frappe never drops
   columns for removed fields, so the data is still sitting in the table.
2. Web Forms don't support Table MultiSelect, so the public /enquiry form's
   "Property" field is dropped rather than left referencing a field that no
   longer exists on Property Lead.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Property Lead"):
        return
    # Superseded by v2_12 (single property + many units), which also reads
    # the old interested_property column directly.
    if not frappe.get_meta("Property Lead").has_field("interested_properties"):
        return

    frappe.db.delete("Web Form Field", {
        "parenttype": "Web Form",
        "fieldname": "interested_property",
    })

    old_values = frappe.db.sql(
        """
        SELECT name, interested_property FROM `tabProperty Lead`
        WHERE interested_property IS NOT NULL AND interested_property != ''
        """,
        as_dict=True,
    )
    for row in old_values:
        if frappe.db.exists("Property Lead Interest", {
            "parenttype": "Property Lead", "parent": row.name, "property": row.interested_property,
        }):
            continue
        doc = frappe.get_doc("Property Lead", row.name)
        doc.append("interested_properties", {"property": row.interested_property})
        doc.save(ignore_permissions=True)

    frappe.db.commit()
