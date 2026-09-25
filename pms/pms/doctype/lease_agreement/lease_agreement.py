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
        self.update_units()
        self.update_status("Active")

    def on_cancel(self):
        self.release_units()
        self.update_status("Terminated")

    # ------------------------------------------------------------
    # Whole-building lease
    # ------------------------------------------------------------
    def fill_whole_building_units(self):
        """Lease Based On = Whole Building:
        replace the units table with EVERY unit of the property.
        All units must be vacant (not held by another lease/booking)."""
        if not self.building:
            frappe.throw("Please select a Property first.")

        all_units = frappe.get_all(
            "Unit",
            filters={"property": self.building},
            fields=[
                "name", "unit_type", "unit_template",
                "floor_no", "area_sqft",
                "monthly_rent", "status",
            ],
        )
        if not all_units:
            frappe.throw(
                f"No units found for property <b>{self.building}</b>."
            )

        occupied = [u.name for u in all_units if u.status == "Occupied"]
        if occupied and self.docstatus == 0:
            frappe.throw(
                "Cannot lease the whole building — these units are "
                "already occupied: <b>" + ", ".join(occupied) + "</b>"
            )

        self.set("units", [])
        for u in all_units:
            self.append("units", {
                "unit_id": u.name,
                "unit_type": u.unit_type,
                "unit_category": u.unit_template,
                "floor_no": u.floor_no,
                "area_sqft": u.area_sqft,
                "monthly_rent": u.monthly_rent,
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

            unit_property = frappe.db.get_value("Unit", row.unit_id, "property")
            if self.building and unit_property and unit_property != self.building:
                frappe.throw(
                    f"Unit <b>{row.unit_id}</b> belongs to property "
                    f"<b>{unit_property}</b>, not <b>{self.building}</b>."
                )

    # ------------------------------------------------------------
    # Facility charges (pulled from each Unit)
    # ------------------------------------------------------------
    def get_unit_facilities(self):
        """Return every ticked facility of every unit on this lease.

        Reads the `facilities` child table of each Unit and keeps only the
        rows where the `value` checkbox is ticked. The amount comes from the
        Unit row; if that is blank we fall back to the `default_amount` of
        the Property Facility master."""
        rows = []
        for unit in self.units or []:
            if not unit.unit_id or not frappe.db.exists("Unit", unit.unit_id):
                continue

            facilities = get_unit_facility_rows(unit.unit_id)

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
                    "Unit", row.unit_id, "monthly_rent"
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
    # Unit occupancy
    # ------------------------------------------------------------
    def update_units(self):
        if not self.units:
            frappe.throw("Please add at least one Unit before submitting.")

        for row in self.units:
            unit_id = row.unit_id
            if not unit_id:
                continue

            if not frappe.db.exists("Unit", unit_id):
                frappe.throw(f"Unit <b>{unit_id}</b> not found.")

            current_status = frappe.db.get_value("Unit", unit_id, "status")
            if current_status == "Occupied":
                frappe.throw(
                    f"Unit <b>{unit_id}</b> is already Occupied. "
                    f"Please select a different unit."
                )

            frappe.db.set_value("Unit", unit_id, {
                "status": "Occupied",
                "current_occupant_start_date": self.start_date,
                "current_occupant_end_date": self.end_date,
            })
            log_occupancy_event(unit_id, "Occupied", lease=self.name)

        frappe.msgprint(
            f"{len(self.units)} Unit(s) marked as Occupied.",
            indicator="green", alert=True,
        )

    def release_units(self):
        for row in self.units or []:
            unit_id = row.unit_id
            if not unit_id or not frappe.db.exists("Unit", unit_id):
                continue
            frappe.db.set_value("Unit", unit_id, {
                "status": "Vacant",
                "current_occupant_start_date": None,
                "current_occupant_end_date": None,
            })
            log_occupancy_event(unit_id, "Vacated", lease=self.name)

        frappe.msgprint(
            "Units released and marked as Vacant.",
            indicator="green", alert=True,
        )


# ------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------
def get_unit_facility_rows(unit_name):
    """Ticked rows of a Unit's `facilities` child table."""
    return frappe.db.sql(
        """
        SELECT facilities, amount, charge_type, remarks
        FROM `tabProperty Facilities`
        WHERE parent = %s
          AND parenttype = 'Unit'
          AND parentfield = 'facilities'
          AND value = 1
        ORDER BY idx
        """,
        unit_name,
        as_dict=True,
    )


def log_occupancy_event(unit, event, lease=None, booking=None):
    """Append-only occupancy history, since Unit itself only stores current
    state (mirrors the Asset-as-unit hack's limitation on purpose — full
    historical backfill from pre-rewrite data is out of scope)."""
    frappe.get_doc({
        "doctype": "Unit Occupancy Log",
        "unit": unit,
        "event": event,
        "event_date": frappe.utils.today(),
        "lease": lease,
        "booking": booking,
    }).insert(ignore_permissions=True)


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
    """Return the ticked facilities of the given Units.

    `units` is a JSON list of Unit names (sent by lease_agreement.js).
    Used by the "Get Facilities From Units" button so the grid fills in
    immediately, without waiting for a save."""
    import json

    if isinstance(units, str):
        units = json.loads(units)

    out = []
    for unit_id in units or []:
        if not unit_id or not frappe.db.exists("Unit", unit_id):
            continue

        unit_info = frappe.db.get_value(
            "Unit", unit_id, ["unit_type", "floor_no"], as_dict=True
        ) or {}

        rows = get_unit_facility_rows(unit_id)

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
                "unit_type": unit_info.get("unit_type"),
                "floor_no": unit_info.get("floor_no"),
            })

    return out
