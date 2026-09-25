# Copyright (c) 2026, admin and contributors
"""Phase 1 rewrite: replace the Asset-as-unit hack with first-class Unit
records.

Every Asset with custom_created_by_pms=1 becomes a Unit. The historical
"Vacent" typo is corrected to "Vacant" in the same write. Ticked Property
Facilities rows are carried over. Old Asset records are left untouched
(not deleted) as a rollback/audit trail for one release cycle.

Every Link field that pointed at these Assets (Lease Agreement Unit.unit_id,
Maintenance Request.unit, Service Apartment Booking.unit, Lease Facility
Charge.unit) is re-pointed at the new Unit using an in-memory Asset->Unit
mapping built while creating the Units, so no temporary breadcrumb field is
needed on Asset.

Idempotent: skipped once every `custom_building_unit_row` group found on
PMS Assets already has a matching Unit.source_row.
"""

import frappe

OCCUPANCY_STATUS_MAP = {
    "Vacent": "Vacant",
    "Occupied": "Occupied",
}

REPOINT_TARGETS = [
    ("Lease Agreement Unit", "unit_id"),
    ("Maintenance Request", "unit"),
    ("Service Apartment Booking", "unit"),
    ("Lease Facility Charge", "unit"),
]


def execute():
    if not frappe.db.exists("DocType", "Unit"):
        return
    if not frappe.db.has_column("Asset", "custom_created_by_pms"):
        # Legacy Asset custom fields already cleaned up — nothing left to read.
        return

    assets = frappe.get_all(
        "Asset",
        filters={"custom_created_by_pms": 1},
        fields=[
            "name", "custom_building", "custom_unit_type", "custom_unit_category",
            "custom_floor_no", "custom_area_sqft", "custom_bedrooms", "custom_bathrooms",
            "custom_monthly_rent", "custom_occupancy_status", "custom_start_date",
            "custom_end_date", "custom_building_unit_row", "custom_inventory_condition",
        ],
        order_by="custom_building_unit_row, creation",
    )
    if not assets:
        return

    already_migrated_rows = set(frappe.get_all("Unit", pluck="source_row"))
    asset_rows = {a.custom_building_unit_row for a in assets if a.custom_building_unit_row}
    if asset_rows and asset_rows.issubset(already_migrated_rows):
        return

    frappe.log_error(
        title="PMS Unit Migration",
        message=(
            f"Dry run: {len(assets)} Asset(s) with custom_created_by_pms=1 "
            f"will become Unit records."
        ),
    )

    asset_to_unit = {}

    for a in assets:
        facility_rows = frappe.get_all(
            "Property Facilities",
            filters={
                "parent": a.name,
                "parenttype": "Asset",
                "parentfield": "custom_property_facility",
            },
            fields=["facilities", "value", "charge_type", "amount", "remarks"],
        )

        unit = frappe.get_doc({
            "doctype": "Unit",
            "property": a.custom_building,
            "unit_type": a.custom_unit_type,
            "unit_template": a.custom_unit_category,
            "floor_no": a.custom_floor_no or 0,
            "area_sqft": a.custom_area_sqft or 0,
            "bedrooms": a.custom_bedrooms or 0,
            "bathrooms": a.custom_bathrooms or 0,
            "monthly_rent": a.custom_monthly_rent or 0,
            "status": OCCUPANCY_STATUS_MAP.get(a.custom_occupancy_status, "Vacant"),
            "current_occupant_start_date": a.custom_start_date,
            "current_occupant_end_date": a.custom_end_date,
            "inventory_condition": a.custom_inventory_condition,
            "source_row": a.custom_building_unit_row,
            "facilities": [
                {
                    "facilities": fr.facilities,
                    "value": fr.value,
                    "charge_type": fr.charge_type,
                    "amount": fr.amount,
                    "remarks": fr.remarks,
                }
                for fr in facility_rows
            ],
        })
        unit.insert(ignore_permissions=True)
        asset_to_unit[a.name] = unit.name

    frappe.db.commit()

    for doctype, fieldname in REPOINT_TARGETS:
        for asset_name, unit_name in asset_to_unit.items():
            frappe.db.sql(
                f"UPDATE `tab{doctype}` SET `{fieldname}` = %s WHERE `{fieldname}` = %s",  # noqa: S608
                (unit_name, asset_name),
            )

    frappe.db.commit()

    frappe.log_error(
        title="PMS Unit Migration",
        message=(
            f"Complete: {len(asset_to_unit)} Unit(s) created; Lease Agreement Unit / "
            f"Maintenance Request / Service Apartment Booking / Lease Facility Charge "
            f"re-pointed from Asset to Unit."
        ),
    )
