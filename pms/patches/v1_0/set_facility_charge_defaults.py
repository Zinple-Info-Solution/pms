# Copyright (c) 2026, admin and contributors
"""Backfill defaults after the facility-charge update.

* Property Facility  -> is_active = 1, charge_type = "Recurring"
* Property Facilities (Asset child rows) -> charge_type = "Recurring"
  and amount copied from the facility master where it is still blank.
"""

import frappe


def execute():
    if frappe.db.has_column("Property Facility", "is_active"):
        frappe.db.sql(
            "UPDATE `tabProperty Facility` SET is_active = 1 WHERE is_active IS NULL"
        )

    if frappe.db.has_column("Property Facility", "charge_type"):
        frappe.db.sql(
            "UPDATE `tabProperty Facility` "
            "SET charge_type = 'Recurring' "
            "WHERE charge_type IS NULL OR charge_type = ''"
        )

    if not frappe.db.has_column("Property Facilities", "charge_type"):
        return

    frappe.db.sql(
        "UPDATE `tabProperty Facilities` "
        "SET charge_type = 'Recurring' "
        "WHERE charge_type IS NULL OR charge_type = ''"
    )

    # Copy the master amount into ticked rows that have no amount yet
    frappe.db.sql(
        """
        UPDATE `tabProperty Facilities` pf
        INNER JOIN `tabProperty Facility` m ON m.name = pf.facilities
        SET pf.amount = m.default_amount
        WHERE pf.value = 1
          AND (pf.amount IS NULL OR pf.amount = 0)
          AND m.default_amount > 0
        """
    )

    frappe.db.commit()
