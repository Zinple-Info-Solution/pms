# Copyright (c) 2026, admin and contributors
"""Phase 1 rewrite: rename the Building doctype to Property.

Building already modelled one-record-per-property; renaming in place (rather
than adding a wrapper Property doctype) avoids a redundant 1:1 join. Safe to
re-run: no-ops once the DocType no longer exists under the old name.
"""

import frappe


def execute():
    if frappe.db.exists("DocType", "Building") and not frappe.db.exists("DocType", "Property"):
        frappe.rename_doc("DocType", "Building", "Property", force=True)
        frappe.db.commit()
