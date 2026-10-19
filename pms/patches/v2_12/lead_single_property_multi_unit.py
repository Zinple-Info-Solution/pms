# Copyright (c) 2026, admin and contributors
"""Property Lead changed from many properties + one unit
(interested_properties Table MultiSelect + interested_unit Link) to one
property + many units (property Link + interested_units Table MultiSelect).

1. Each lead's property becomes its first old Interested Property (or the
   even older single interested_property column, on a site that skipped
   v2_11), or else the property of its old Interested Unit.
2. The old Interested Unit is carried into Interested Units when it belongs
   to that property.
3. The now-unused Property Lead Interest child doctype is dropped.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Property Lead"):
        return

    first_property = {}
    if frappe.db.table_exists("Property Lead Interest"):
        for row in frappe.db.sql(
            """
            SELECT parent, property FROM `tabProperty Lead Interest`
            WHERE parenttype = 'Property Lead'
            ORDER BY parent, idx
            """,
            as_dict=True,
        ):
            first_property.setdefault(row.parent, row.property)

    if frappe.db.has_column("Property Lead", "interested_property"):
        for name, prop in frappe.db.sql(
            """
            SELECT name, interested_property FROM `tabProperty Lead`
            WHERE interested_property IS NOT NULL AND interested_property != ''
            """
        ):
            first_property.setdefault(name, prop)

    old_unit = {}
    if frappe.db.has_column("Property Lead", "interested_unit"):
        old_unit = dict(frappe.db.sql(
            """
            SELECT name, interested_unit FROM `tabProperty Lead`
            WHERE interested_unit IS NOT NULL AND interested_unit != ''
            """
        ))

    for lead in set(first_property) | set(old_unit):
        doc = frappe.get_doc("Property Lead", lead)
        if doc.property:
            continue

        unit = old_unit.get(lead)
        unit_property = frappe.db.get_value("Unit", unit, "property") if unit else None
        doc.property = first_property.get(lead) or unit_property
        if unit and unit_property == doc.property:
            doc.append("interested_units", {"unit": unit})
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

    if frappe.db.exists("DocType", "Property Lead Interest"):
        frappe.delete_doc("DocType", "Property Lead Interest", ignore_missing=True, force=True)

    frappe.db.commit()
