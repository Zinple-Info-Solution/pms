# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt, add_months, add_days, getdate, formatdate, month_diff

FREQUENCY_MONTHS = {
    "Monthly": 1,
    "Quarterly": 3,
    "Half-Yearly": 6,
    "Yearly": 12,
}


class LeaseAgreement(Document):

    def validate(self):
        self.validate_dates()
        if self.lease_based_on == "Whole Building":
            self.fill_whole_building_units()
        self.validate_units()
        self.sync_facility_charges()
        self.calculate_totals()
        if self.docstatus == 0:
            self.generate_rent_schedule()

    def on_submit(self):
        self.update_assets()
        self.update_status("Active")

    def on_cancel(self):
        self.release_assets()
        self.update_status("Terminated")

    # ------------------------------------------------------------
    # Whole-building lease
    # ------------------------------------------------------------
    def fill_whole_building_units(self):
        """Lease Based On = Whole Building:
        replace the units table with EVERY unit of the building.
        All units must be vacant (not held by another lease/booking)."""
        if not self.building:
            frappe.throw("Please select a Building first.")

        all_units = frappe.get_all(
            "Asset",
            filters={
                "custom_building": self.building,
                "custom_created_by_pms": 1,
                "docstatus": 1,
            },
            fields=[
                "name", "custom_unit_type", "custom_unit_category",
                "custom_floor_no", "custom_area_sqft",
                "custom_monthly_rent", "custom_occupancy_status",
            ],
        )
        if not all_units:
            frappe.throw(
                f"No submitted units found for building <b>{self.building}</b>."
            )

        occupied = [u.name for u in all_units
                    if u.custom_occupancy_status == "Occupied"]
        if occupied and self.docstatus == 0:
            frappe.throw(
                "Cannot lease the whole building — these units are "
                "already occupied: <b>" + ", ".join(occupied) + "</b>"
            )

        self.set("units", [])
        for u in all_units:
            self.append("units", {
                "unit_id": u.name,
                "unit_type": u.custom_unit_type,
                "unit_category": u.custom_unit_category,
                "floor_no": u.custom_floor_no,
                "area_sqft": u.custom_area_sqft,
                "monthly_rent": u.custom_monthly_rent,
            })

    # ------------------------------------------------------------
    # Validations
    # ------------------------------------------------------------
    def validate_dates(self):
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw("End Date must be after Start Date.")

    def validate_units(self):
        seen = set()
        for row in self.units or []:
            if not row.unit_id:
                continue
            if row.unit_id in seen:
                frappe.throw(
                    f"Unit <b>{row.unit_id}</b> is added more than once (Row #{row.idx})."
                )
            seen.add(row.unit_id)

            asset_building = frappe.db.get_value("Asset", row.unit_id, "custom_building")
            if self.building and asset_building and asset_building != self.building:
                frappe.throw(
                    f"Unit <b>{row.unit_id}</b> belongs to building "
                    f"<b>{asset_building}</b>, not <b>{self.building}</b>."
                )

    # ------------------------------------------------------------
    # Facility charges (pulled from each unit's Asset)
    # ------------------------------------------------------------
    def get_unit_facilities(self):
        """Return every ticked facility of every unit on this lease.

        Reads the `custom_property_facility` child table of each Asset and
        keeps only the rows where the `value` checkbox is ticked. The amount
        comes from the Asset row; if that is blank we fall back to the
        `default_amount` of the Property Facility master."""
        rows = []
        for unit in self.units or []:
            if not unit.unit_id or not frappe.db.exists("Asset", unit.unit_id):
                continue

            facilities = get_asset_facility_rows(unit.unit_id)

            for f in facilities:
                if not f.facilities:
                    continue

                master = frappe.db.get_value(
                    "Property Facility", f.facilities,
                    ["default_amount", "charge_type", "is_active"],
                    as_dict=True,
                ) or {}

                if master.get("is_active") == 0:
                    continue

                rows.append({
                    "unit": unit.unit_id,
                    "facility": f.facilities,
                    "amount": flt(f.amount) or flt(master.get("default_amount")),
                    "charge_type": f.charge_type or master.get("charge_type") or "Recurring",
                    "remarks": f.remarks,
                    "unit_type": unit.unit_type,
                    "floor_no": unit.floor_no,
                })
        return rows

    def sync_facility_charges(self):
        """Keep the Facility Charges table in sync with the units.

        * new ticked facilities are appended
        * facilities of units that were removed from the lease are dropped
        * amounts / Apply flags edited by the user are preserved
        * manually added rows (no unit) are always kept
        """
        if self.docstatus != 0:
            return
        if not self.get("auto_fetch_facilities"):
            return

        old = {}
        manual = []
        for row in self.get("facilities") or []:
            if row.auto_fetched and row.unit:
                old[(row.unit, row.facility)] = row
            else:
                manual.append(row)

        wanted = self.get_unit_facilities()

        self.set("facilities", [])

        for row in manual:
            self.append("facilities", {
                "apply": row.apply,
                "unit": row.unit,
                "facility": row.facility,
                "charge_type": row.charge_type,
                "amount": row.amount,
                "unit_type": row.unit_type,
                "floor_no": row.floor_no,
                "remarks": row.remarks,
                "auto_fetched": 0,
            })

        for f in wanted:
            prev = old.get((f["unit"], f["facility"]))
            self.append("facilities", {
                "apply": prev.apply if prev else 1,
                "unit": f["unit"],
                "facility": f["facility"],
                # keep the user's edited amount, otherwise take the unit's amount
                "charge_type": prev.charge_type if prev else f["charge_type"],
                "amount": prev.amount if prev else f["amount"],
                "unit_type": f["unit_type"],
                "floor_no": f["floor_no"],
                "remarks": (prev.remarks if prev else f["remarks"]),
                "auto_fetched": 1,
            })

    def calculate_facility_charges(self):
        """Split the Facility Charges table into monthly / one-time totals."""
        monthly = one_time = 0
        for row in self.get("facilities") or []:
            if not row.apply:
                continue
            if row.charge_type == "One Time":
                one_time += flt(row.amount)
            else:
                monthly += flt(row.amount)

        self.facility_charges_monthly = monthly
        self.facility_charges_one_time = one_time
        return monthly, one_time

    # ------------------------------------------------------------
    # Totals: rent + charges - discount
    # ------------------------------------------------------------
    def calculate_totals(self):
        total = 0
        for row in self.units or []:
            if row.unit_id and not flt(row.monthly_rent):
                row.monthly_rent = frappe.db.get_value(
                    "Asset", row.unit_id, "custom_monthly_rent"
                ) or 0
            total += flt(row.monthly_rent)

        self.total_rent = total
        if not flt(self.rent_amount):
            self.rent_amount = total

        monthly_rent = flt(self.rent_amount) or total

        # Facility charges coming from the units
        facility_monthly, facility_one_time = self.calculate_facility_charges()

        # Additional charges + facility charges
        self.monthly_charges = sum(
            flt(c.amount) for c in (self.additional_charges or [])
            if c.charge_type == "Recurring"
        ) + facility_monthly

        self.one_time_charges = sum(
            flt(c.amount) for c in (self.additional_charges or [])
            if c.charge_type == "One Time"
        ) + facility_one_time

        # Discount (per month, applied on rent)
        if self.discount_type == "Percentage":
            if flt(self.discount_value) > 100:
                frappe.throw("Discount percentage cannot exceed 100%.")
            self.discount_per_month = monthly_rent * flt(self.discount_value) / 100
        elif self.discount_type == "Amount":
            self.discount_per_month = flt(self.discount_value)
        else:
            self.discount_per_month = 0

        if flt(self.discount_per_month) > monthly_rent + flt(self.monthly_charges):
            frappe.throw("Discount cannot be more than rent + recurring charges.")

        self.net_monthly_amount = (
            monthly_rent + flt(self.monthly_charges) - flt(self.discount_per_month)
        )

    # ------------------------------------------------------------
    # Rent schedule generation
    # ------------------------------------------------------------
    def generate_rent_schedule(self):
        """(Re)build the rent collection schedule while the lease is a draft.
        One row per billing cycle from start_date to end_date."""
        if not (self.start_date and self.end_date):
            return

        cycle = FREQUENCY_MONTHS.get(self.billing_frequency or "Monthly", 1)
        monthly_rent = flt(self.rent_amount) or flt(self.total_rent)

        self.set("rent_schedule", [])

        period_start = getdate(self.start_date)
        lease_end = getdate(self.end_date)
        first = True

        while period_start <= lease_end:
            period_end = min(add_days(add_months(period_start, cycle), -1), lease_end)

            # Months in this period (prorated for a short last cycle)
            months = month_diff(period_end, period_start)
            months = min(months, cycle)

            rent = monthly_rent * months
            charges = flt(self.monthly_charges) * months
            if first:
                charges += flt(self.one_time_charges)
            discount = flt(self.discount_per_month) * months

            self.append("rent_schedule", {
                "due_date": period_start,
                "billing_period": f"{formatdate(period_start)} → {formatdate(period_end)}",
                "rent_amount": rent,
                "charges_amount": charges,
                "discount_amount": discount,
                "total_amount": rent + charges - discount,
                "status": "Pending",
            })

            period_start = add_months(period_start, cycle)
            first = False

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def update_status(self, status):
        self.db_set("status", status)

    # ------------------------------------------------------------
    # Asset occupancy
    # ------------------------------------------------------------
    def update_assets(self):
        if not self.units:
            frappe.throw("Please add at least one Unit before submitting.")

        for row in self.units:
            unit_id = row.unit_id
            if not unit_id:
                continue

            if not frappe.db.exists("Asset", unit_id):
                frappe.throw(f"Asset <b>{unit_id}</b> not found.")

            current_status = frappe.db.get_value(
                "Asset", unit_id, "custom_occupancy_status"
            )
            if current_status == "Occupied":
                frappe.throw(
                    f"Asset <b>{unit_id}</b> is already Occupied. "
                    f"Please select a different unit."
                )

            frappe.db.set_value("Asset", unit_id, {
                "custom_occupancy_status": "Occupied",
                "custom_start_date": self.start_date,
                "custom_end_date": self.end_date,
            })

        frappe.msgprint(
            f"{len(self.units)} Asset(s) marked as Occupied.",
            indicator="green", alert=True,
        )

    def release_assets(self):
        for row in self.units or []:
            unit_id = row.unit_id
            if not unit_id or not frappe.db.exists("Asset", unit_id):
                continue
            frappe.db.set_value("Asset", unit_id, {
                "custom_occupancy_status": "Vacent",
                "custom_start_date": None,
                "custom_end_date": None,
            })

        frappe.msgprint(
            "Assets released and marked as Vacant.",
            indicator="green", alert=True,
        )


# ------------------------------------------------------------
# Shared helper
# ------------------------------------------------------------
def get_asset_facility_rows(asset_name):
    """Ticked rows of an Asset's `custom_property_facility` child table."""
    return frappe.db.sql(
        """
        SELECT facilities, amount, charge_type, remarks
        FROM `tabProperty Facilities`
        WHERE parent = %s
          AND parenttype = 'Asset'
          AND parentfield = 'custom_property_facility'
          AND value = 1
        ORDER BY idx
        """,
        asset_name,
        as_dict=True,
    )


# ------------------------------------------------------------
# Lease renewal
# ------------------------------------------------------------
@frappe.whitelist()
def make_renewal(lease_name):
    """Create a draft renewal lease continuing right after the old one,
    with the same duration, units, charges and discount."""
    old = frappe.get_doc("Lease Agreement", lease_name)
    if old.docstatus != 1:
        frappe.throw("Only a submitted lease can be renewed.")

    duration_days = (getdate(old.end_date) - getdate(old.start_date)).days
    new_start = add_days(getdate(old.end_date), 1)
    new_end = add_days(new_start, duration_days)

    new_lease = frappe.copy_doc(old)
    new_lease.start_date = new_start
    new_lease.end_date = new_end
    new_lease.status = ""
    new_lease.set("rent_schedule", [])
    new_lease.insert()

    frappe.msgprint(
        f"Renewal lease <b>{new_lease.name}</b> created "
        f"({new_start} → {new_end}). Review and submit it.",
        indicator="green",
    )
    return new_lease.name


# ------------------------------------------------------------
# Facility helpers used by the client script
# ------------------------------------------------------------
@frappe.whitelist()
def get_facilities_for_units(units):
    """Return the ticked facilities of the given Assets.

    `units` is a JSON list of Asset names (sent by lease_agreement.js).
    Used by the "Get Facilities From Units" button so the grid fills in
    immediately, without waiting for a save."""
    import json

    if isinstance(units, str):
        units = json.loads(units)

    out = []
    for unit_id in units or []:
        if not unit_id or not frappe.db.exists("Asset", unit_id):
            continue

        unit_info = frappe.db.get_value(
            "Asset", unit_id, ["custom_unit_type", "custom_floor_no"], as_dict=True
        ) or {}

        rows = get_asset_facility_rows(unit_id)

        for r in rows:
            if not r.facilities:
                continue

            master = frappe.db.get_value(
                "Property Facility", r.facilities,
                ["default_amount", "charge_type", "is_active"],
                as_dict=True,
            ) or {}

            if master.get("is_active") == 0:
                continue

            out.append({
                "unit": unit_id,
                "facility": r.facilities,
                "amount": flt(r.amount) or flt(master.get("default_amount")),
                "charge_type": r.charge_type or master.get("charge_type") or "Recurring",
                "remarks": r.remarks,
                "unit_type": unit_info.get("custom_unit_type"),
                "floor_no": unit_info.get("custom_floor_no"),
            })

    return out
