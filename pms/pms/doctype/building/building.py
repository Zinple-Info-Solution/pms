# Copyright (c) 2026, admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Building(Document):
    def on_update(self):
        self.sync_rooms()

    def sync_rooms(self):
        series_map = {
            "Apartment": "APT-.MM.-.DD.-.####",
            "Shop": "SH-.MM.-.DD.-.####",
            "Gym": "GYM-.MM.-.DD.-.####",
        }

        rows = self.get("units") or []

        for row in rows:
            required = row.unit_no or 0

            existing = frappe.db.count(
                "Building Units",
                filters={"building_unit_row": row.name}
            )

            if existing < required:
                to_create = required - existing
                for _ in range(to_create):
                    room = frappe.new_doc("Building Units")
                    room.naming_series = series_map.get(row.unit_type)
                    room.building = self.name            # 👈 proper Link reference
                    room.property_name = self.building_name  # 👈 readable label
                    room.unit_category = row.unit_category
                    room.unit_type = row.unit_type
                    room.area_sqft = row.area_sqft
                    room.length_ft = row.length_ft
                    room.width_ft = row.width_ft
                    room.bathrooms = row.bathrooms
                    room.monthly_rent = row.monthly_rent
                    room.building_unit_row = row.name
                    room.insert(ignore_permissions=True)

            elif existing > required:
                frappe.msgprint(
                    f"Row {row.idx}: unit count reduced. "
                    f"{existing - required} existing Room record(s) were left untouched."
                )