# Copyright (c) 2026, admin and contributors
"""Phase 2 cleanup: Custom Field fixture sync is additive-only in this
Frappe version — removing `custom_unit_no` from
pms/pms/custom/sales_invoice_item.json does not drop the underlying
Custom Field or column on its own. Delete it explicitly now that
`custom_unit` (Link -> Unit) has taken over its role.
"""

import frappe


def execute():
    if frappe.db.exists("Custom Field", "Sales Invoice Item-custom_unit_no"):
        frappe.delete_doc("Custom Field", "Sales Invoice Item-custom_unit_no", ignore_permissions=True)
        frappe.db.commit()
