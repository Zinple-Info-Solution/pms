# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt, add_months, add_days, getdate, formatdate, month_diff
from pms.pms.doctype.unit.unit import sync_unit_listing

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
        self.create_deposit_and_first_invoice()

    def on_cancel(self):
        self.release_units()
        self.update_status("Terminated")

    @frappe.whitelist()
    def send_for_signature(self):
        """Send this draft lease to the tenant for e-signature via Zoho
        Sign. A separate, explicit action rather than something that fires
        the moment the draft is created, since the lease's dates/terms
        often still need adjusting right after generation — staff decide
        when it's actually ready to go out."""
        if self.docstatus != 0:
            frappe.throw("Only a draft Lease Agreement can be sent for signature.")

        from pms.pms.integrations.esign import send_for_esign, is_enabled
        if not is_enabled():
            frappe.throw(
                "E-sign isn't configured yet — turn it on and add Zoho Sign "
                "credentials in PMS Integration Settings first."
            )

        if send_for_esign(self):
            frappe.msgprint(
                "Sent to the tenant for e-signature.", indicator="green", alert=True
            )
        else:
            frappe.throw(
                "Couldn't send for e-signature — check the Error Log for details."
            )

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

        carried_over = self.get_renewed_units()
        unavailable = [
            u.name for u in all_units
            if u.status in ("Occupied", "Reserved", "Notice Given") and u.name not in carried_over
        ]
        if unavailable and self.docstatus == 0:
            frappe.throw(
                "Cannot lease the whole building — these units are "
                "not available: <b>" + ", ".join(unavailable) + "</b>"
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
    # Rent escalation
    # ------------------------------------------------------------
    def apply_rent_escalation(self, row):
        """Bump rent_amount per the escalation row and rescale every not-yet-
        invoiced future Rent Schedule row's rent_amount/total_amount
        proportionally (Invoiced/Paid rows are historical and untouched)."""
        old_rent = flt(self.rent_amount)
        if not old_rent:
            frappe.throw("Cannot apply escalation: lease has no Rent Amount set.")

        if row.escalation_type == "Percentage":
            new_rent = old_rent * (1 + flt(row.escalation_value) / 100)
        else:
            new_rent = old_rent + flt(row.escalation_value)

        ratio = new_rent / old_rent
        self.db_set("rent_amount", new_rent)

        for sr in self.rent_schedule:
            if sr.status == "Pending" and getdate(sr.due_date) >= getdate(row.escalation_date):
                new_rent_component = flt(sr.rent_amount) * ratio
                new_total = new_rent_component + flt(sr.charges_amount) - flt(sr.discount_amount)
                frappe.db.set_value("Rent Schedule", sr.name, {
                    "rent_amount": new_rent_component,
                    "total_amount": new_total,
                })

        row.db_set("applied", 1)
        row.db_set("new_rent_amount", new_rent)

    # ------------------------------------------------------------
    # Unit occupancy
    # ------------------------------------------------------------
    def update_units(self):
        """Lease submission reserves the unit (not yet Occupied — that
        happens on Move In, so there's a real state for "signed but the
        tenant hasn't moved in yet")."""
        if not self.units:
            frappe.throw("Please add at least one Unit before submitting.")

        carried_over = self.get_renewed_units()
        reserved = 0
        for row in self.units:
            unit_id = row.unit_id
            if not unit_id:
                continue

            if not frappe.db.exists("Unit", unit_id):
                frappe.throw(f"Unit <b>{unit_id}</b> not found.")

            if unit_id in carried_over:
                # Same tenant, already in the unit under the lease being
                # renewed — keep its status, just extend the occupancy.
                frappe.db.set_value("Unit", unit_id, "current_occupant_end_date", self.end_date)
                continue

            current_status = frappe.db.get_value("Unit", unit_id, "status")
            if current_status in ("Reserved", "Occupied"):
                frappe.throw(
                    f"Unit <b>{unit_id}</b> is already {current_status}. "
                    f"Please select a different unit."
                )

            frappe.db.set_value("Unit", unit_id, {
                "status": "Reserved",
                "current_occupant_start_date": self.start_date,
                "current_occupant_end_date": self.end_date,
            })
            sync_unit_listing(unit_id, "Reserved")
            log_occupancy_event(unit_id, "Reserved", lease=self.name)
            reserved += 1

        if reserved:
            frappe.msgprint(
                f"{reserved} Unit(s) marked as Reserved.",
                indicator="green", alert=True,
            )

    def get_renewed_units(self):
        """Units this lease takes over from the lease it renews, while that
        lease is still running. Once it has expired (units released to
        Vacant) or been terminated, the units are reserved afresh."""
        if not self.renewed_from:
            return set()
        old = frappe.db.get_value(
            "Lease Agreement", self.renewed_from, ["docstatus", "status"], as_dict=True
        )
        if not old or old.docstatus != 1 or old.status not in ("Active", "Notice Given"):
            return set()
        return set(frappe.get_all(
            "Lease Agreement Unit", filters={"parent": self.renewed_from}, pluck="unit_id"
        ))

    def create_deposit_and_first_invoice(self):
        """On lease submission: invoice the security deposit (if any) and
        the first rent cycle, with a payment link emailed to the tenant."""
        from pms.pms.billing import make_deposit_invoice, make_rent_invoice, email_invoice_to_tenant

        # A renewal keeps the deposit already held under the previous lease.
        if flt(self.security_deposit) > 0 and not self.renewed_from:
            deposit_invoice = make_deposit_invoice(self.name)
            if deposit_invoice:
                email_invoice_to_tenant(deposit_invoice)

        if self.rent_schedule:
            first_row = self.rent_schedule[0]
            if first_row.status == "Pending":
                rent_invoice = make_rent_invoice(self.name, first_row.name)
                email_invoice_to_tenant(rent_invoice)

    def release_units(self):
        carried_over = self.get_renewed_units()
        old_end_date = (
            frappe.db.get_value("Lease Agreement", self.renewed_from, "end_date")
            if carried_over else None
        )
        for row in self.units or []:
            unit_id = row.unit_id
            if not unit_id or not frappe.db.exists("Unit", unit_id):
                continue
            if unit_id in carried_over:
                # Cancelling a renewal hands the unit back to the lease it
                # renewed, which is still running.
                frappe.db.set_value("Unit", unit_id, "current_occupant_end_date", old_end_date)
                continue
            frappe.db.set_value("Unit", unit_id, {
                "status": "Vacant",
                "current_occupant_start_date": None,
                "current_occupant_end_date": None,
            })
            sync_unit_listing(unit_id, "Vacant")
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


def get_lease_chain(lease_name):
    """This lease plus the leases it renewed, newest first — a renewal
    has no Move In of its own; the tenant moved in under the original."""
    chain = []
    while lease_name and lease_name not in chain:
        chain.append(lease_name)
        lease_name = frappe.db.get_value("Lease Agreement", lease_name, "renewed_from")
    return chain


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
def make_renewal(lease_name, rent_increase_percent=0, start_date=None, end_date=None):
    """Create a draft renewal lease continuing right after the old one,
    with the same units, charges and discount. Rent (per unit and the
    lease's Rent Amount) goes up by `rent_increase_percent`. Dates default
    to the day after the old lease ends, for the same duration."""
    old = frappe.get_doc("Lease Agreement", lease_name)
    if old.docstatus != 1:
        frappe.throw("Only a submitted lease can be renewed.")

    increase = flt(rent_increase_percent)
    if increase < 0:
        frappe.throw("Rent increase percentage cannot be negative.")
    factor = 1 + increase / 100

    existing = frappe.db.get_value(
        "Lease Agreement", {"renewed_from": old.name, "docstatus": ["<", 2]}, "name"
    )
    if existing:
        frappe.throw(f"Lease <b>{old.name}</b> already has a renewal: <b>{existing}</b>.")

    new_start = getdate(start_date) if start_date else add_days(getdate(old.end_date), 1)
    if end_date:
        new_end = getdate(end_date)
    else:
        duration_days = (getdate(old.end_date) - getdate(old.start_date)).days
        new_end = add_days(new_start, duration_days)

    new_lease = frappe.copy_doc(old)
    new_lease.start_date = new_start
    new_lease.end_date = new_end
    new_lease.status = ""
    new_lease.renewed_from = old.name
    new_lease.rent_increase_percent = increase
    new_lease.rent_amount = flt(flt(old.rent_amount) * factor, 2)
    for row in new_lease.units:
        row.monthly_rent = flt(flt(row.monthly_rent) * factor, 2)
    new_lease.set("rent_schedule", [])
    # Escalation rows are dated within the old term.
    new_lease.set("rent_escalation", [])
    new_lease.insert()

    frappe.msgprint(
        f"Renewal lease <b>{new_lease.name}</b> created "
        f"({new_start} → {new_end}"
        f"{f', rent +{increase:g}%' if increase else ''}). Review and submit it.",
        indicator="green",
    )
    return new_lease.name


# ------------------------------------------------------------
# Move-in
# ------------------------------------------------------------
@frappe.whitelist()
def make_move_in(lease_name, unit=None):
    """Create a draft Move In for a submitted lease. If the lease has a
    single unit, it's pre-filled; multi-unit leases require the caller to
    pass `unit`."""
    lease = frappe.get_doc("Lease Agreement", lease_name)
    if lease.docstatus != 1:
        frappe.throw("Only a submitted lease can have a Move In recorded.")

    if not unit:
        if len(lease.units) != 1:
            frappe.throw(
                "This lease has more than one unit — please specify which "
                "unit is moving in."
            )
        unit = lease.units[0].unit_id

    from pms.pms.doctype.move_in.move_in import get_default_checklist_template

    move_in = frappe.get_doc({
        "doctype": "Move In",
        "lease": lease.name,
        "unit": unit,
        "tenant": lease.tenant,
        "move_in_date": lease.start_date,
        "checklist_template": get_default_checklist_template(),
    })
    move_in.insert()

    frappe.msgprint(
        f"Move In <b>{move_in.name}</b> created. Review and submit it.",
        indicator="green",
    )
    return move_in.name


# ------------------------------------------------------------
# Move-out
# ------------------------------------------------------------
@frappe.whitelist()
def make_move_out(lease_name, unit=None):
    """Create a draft Move Out for a submitted lease, mirroring the
    make_renewal() pattern. If the lease has a single unit, it's
    pre-filled; multi-unit leases require the caller to pass `unit`."""
    lease = frappe.get_doc("Lease Agreement", lease_name)
    if lease.docstatus != 1:
        frappe.throw("Only a submitted lease can be moved out.")

    if not unit:
        if len(lease.units) != 1:
            frappe.throw(
                "This lease has more than one unit — please specify which "
                "unit is moving out."
            )
        unit = lease.units[0].unit_id

    move_out = frappe.get_doc({
        "doctype": "Move Out",
        "lease": lease.name,
        "unit": unit,
        "tenant": lease.tenant,
        "move_out_date": lease.end_date,
    })
    # Check the same items the tenant moved in with, starting from their
    # move-in condition, so the deposit settlement compares like with like.
    move_in = frappe.db.get_value(
        "Move In",
        {"lease": ["in", get_lease_chain(lease.name)], "unit": unit, "docstatus": 1},
        ["name", "checklist_template"], as_dict=True, order_by="creation desc",
    )
    if move_in:
        move_out.checklist_template = move_in.checklist_template
        for row in frappe.get_all(
            "Move In Checklist Item",
            filters={"parent": move_in.name, "parenttype": "Move In"},
            fields=["item", "condition"], order_by="idx",
        ):
            move_out.append("condition_checklist", row)
    else:
        from pms.pms.doctype.move_in.move_in import get_default_checklist_template
        move_out.checklist_template = get_default_checklist_template()
    move_out.insert()

    frappe.msgprint(
        f"Move Out <b>{move_out.name}</b> created. Review and submit it.",
        indicator="green",
    )
    return move_out.name


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
