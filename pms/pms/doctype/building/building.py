# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class Building(Document):

    def on_update(self):
        self.ensure_asset_categories_exist()
        self.ensure_location_exists()
        self.sync_units()

    def ensure_item_for_unit_type(self, unit_type, asset_category):
        """Create item like 'Building Unit-Apartment' if not exists"""
        item_code = f"Building Unit-{unit_type}"

        if not frappe.db.exists("Item", item_code):
            item = frappe.get_doc({
                "doctype"        : "Item",
                "item_code"      : item_code,
                "item_name"      : item_code,
                "item_group"     : "All Item Groups",
                "is_fixed_asset" : 1,
                "is_stock_item"  : 0,
                "asset_category" : asset_category,
            })
            try:
                item.insert(ignore_permissions=True)
                frappe.db.commit()
                frappe.msgprint(
                    f"✅ Item <b>{item_code}</b> created automatically.",
                    indicator="green",
                    alert=True
                )
            except Exception as e:
                frappe.log_error(str(e), f"Item Creation Error: {item_code}")

        return item_code

    def ensure_asset_categories_exist(self):
        """Make sure Asset Categories exist"""
        for category in ["Residential", "Commercial", "Mixed Use"]:
            if not frappe.db.exists("Asset Category", category):
                cat = frappe.get_doc({
                    "doctype"                 : "Asset Category",
                    "asset_category_name"     : category,
                    "enable_cwip_accounting"  : 0,
                    "non_depreciable_category": 1,
                })
                try:
                    cat.insert(ignore_permissions=True)
                    frappe.db.commit()
                except Exception as e:
                    frappe.log_error(str(e), "Asset Category Creation Error")

    def ensure_location_exists(self):
        """Create a Location for this Building if not exists"""
        if not frappe.db.exists("Location", self.building_name):
            loc = frappe.get_doc({
                "doctype"       : "Location",
                "location_name" : self.building_name,
            })
            try:
                loc.insert(ignore_permissions=True)
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(str(e), "Location Creation Error")

    def sync_units(self):
        asset_category_map = {
            "Apartment" : "Residential",
            "Villa"     : "Residential",
            "Shop"      : "Commercial",
            "Office"    : "Commercial",
            "Gym"       : "Mixed Use",
            "Parking"   : "Commercial",
            "Warehouse" : "Commercial",
        }

        company = (
            frappe.defaults.get_user_default("Company") or
            frappe.db.get_single_value("Global Defaults", "default_company")
        )

        rows = self.get("units") or []
        total_created = 0

        for row in rows:
            required  = row.unit_no or 0
            unit_type = row.unit_type or "Apartment"
            asset_category = asset_category_map.get(unit_type, "Residential")

            # Ensure item exists for this unit type
            item_code = self.ensure_item_for_unit_type(unit_type, asset_category)

            # ✅ Count existing assets per row (not whole building)
            existing = frappe.db.count(
                "Asset",
                filters={
                    "custom_building"          : self.name,
                    "custom_building_unit_row" : row.name,  # ✅ per row
                    "custom_created_by_pms"    : 1
                }
            )

            frappe.log_error(
                f"Row {row.idx} ({unit_type}): required={required}, existing={existing}",
                "PMS Sync Debug"
            )

            if existing < required:
                to_create = required - existing

                for i in range(to_create):
                    unit_number = existing + i + 1
                    asset_name  = f"{self.building_name} - {unit_type} - {unit_number}"

                    asset = frappe.get_doc({
                        "doctype"                : "Asset",
                        "item_code"              : item_code,
                        "asset_name"             : asset_name,
                        "asset_category"         : asset_category,
                        "company"                : company,
                        "purchase_date"          : frappe.utils.today(),
                        "available_for_use_date" : frappe.utils.today(),
                        "location"               : self.building_name,
                        "gross_purchase_amount"  : (row.monthly_rent or 0) * 12,
                        "calculate_depreciation" : 0,
                        "is_existing_asset"      : 1,
                        # PMS custom fields
                        "custom_created_by_pms"  : 1,
                        "custom_occupancy_status": "Vacent",
                        "custom_building"        : self.name,
                        "custom_property_name"   : self.building_name,
                        "custom_unit_type"       : unit_type,
                        "custom_unit_category"   : row.unit_category,
                        "custom_area_sqft"       : row.area_sqft or 0,
                        "custom_length_ft"       : row.length_ft or 0,
                        "custom_width_ft"        : row.width_ft or 0,
                        "custom_bathrooms"       : row.bathrooms or 0,
                        "custom_monthly_rent"    : row.monthly_rent or 0,
                        "custom_building_unit_row": row.name,  # ✅ link to row
                        "custom_floor_no"        : row.get("floor_no") or 0,
                    })

                    try:
                        asset.insert(ignore_permissions=True)
                        total_created += 1
                    except Exception as e:
                        frappe.log_error(
                            f"Failed to create Asset '{asset_name}': {str(e)}",
                            "PMS Asset Creation Error"
                        )

            elif existing > required:
                frappe.msgprint(
                    f"Row {row.idx} ({unit_type}): count reduced. "
                    f"{existing - required} existing Asset(s) left untouched.",
                    indicator="orange",
                    alert=True
                )

            elif existing == required:
                frappe.msgprint(
                    f"Row {row.idx} ({unit_type}): already has {existing} asset(s). No changes.",
                    indicator="blue",
                    alert=True
                )

        frappe.db.commit()
        frappe.msgprint(
            f"✅ Assets synced for <b>{self.building_name}</b> — {total_created} new asset(s) created.",
            indicator="green",
            alert=True
        )