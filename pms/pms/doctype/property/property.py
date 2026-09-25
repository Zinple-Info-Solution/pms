# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class Property(Document):

    def on_update(self):
        self.ensure_location_exists()
        self.sync_units()

    def ensure_location_exists(self):
        """Create a Location for this Property if not exists (used by real
        fixed Assets — AC, furniture, etc. — nested inside a Unit)."""
        if not frappe.db.exists("Location", self.building_name):
            try:
                frappe.get_doc({
                    "doctype"       : "Location",
                    "location_name" : self.building_name,
                }).insert(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(str(e), "PMS Location Creation Error")

    def sync_units(self):
        """Create Unit records from the `units` template/count rows.
        Only ever grows the Unit count for a row — if a row's count is
        reduced, existing Units are left untouched and a warning is shown
        (matching the historical behaviour, now made explicit rather than
        silent)."""
        rows = self.get("units") or []
        total_created = 0

        for row in rows:
            required = row.unit_no or 0
            if required <= 0:
                continue

            existing = frappe.db.count(
                "Unit",
                filters={"property": self.name, "source_row": row.name},
            )

            if existing < required:
                for _ in range(required - existing):
                    try:
                        frappe.get_doc({
                            "doctype"      : "Unit",
                            "property"     : self.name,
                            "unit_type"    : row.unit_type,
                            "unit_template": row.unit_category,
                            "floor_no"     : row.get("floor_no") or 0,
                            "area_sqft"    : row.area_sqft or 0,
                            "bedrooms"     : row.bedrooms or 0,
                            "bathrooms"    : row.bathrooms or 0,
                            "monthly_rent" : row.monthly_rent or 0,
                            "status"       : "Vacant",
                            "source_row"   : row.name,
                        }).insert(ignore_permissions=True)
                        total_created += 1
                    except Exception as e:
                        frappe.log_error(
                            f"Failed to create Unit for row '{row.name}': {e}",
                            "PMS Unit Creation Error",
                        )
            elif existing > required:
                frappe.msgprint(
                    f"Row {row.idx} ({row.unit_type}): count reduced. "
                    f"{existing - required} existing Unit(s) left untouched.",
                    indicator="orange", alert=True,
                )

        if total_created:
            frappe.msgprint(
                f"✅ {total_created} new unit(s) created for <b>{self.building_name}</b>.",
                indicator="green", alert=True,
            )
