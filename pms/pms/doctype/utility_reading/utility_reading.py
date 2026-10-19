# Copyright (c) 2026, admin and contributors
"""Metered utility consumption for one unit on a lease. Pending readings are
added to the lease's next rent invoice (billing.make_rent_invoice), or
invoiced on their own with Create Invoice (e.g. the final reading at
move-out, after the last rent cycle has been billed)."""

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class UtilityReading(Document):

    def validate(self):
        self.validate_not_invoiced()
        self.validate_unit_on_lease()
        if not self.previous_reading:
            self.previous_reading = get_previous_reading(
                self.unit, self.utility_type, self.lease, self.reading_date, self.name
            )
        if not flt(self.rate_per_unit):
            self.rate_per_unit = get_last_rate(self.unit, self.utility_type, self.name)

        if flt(self.current_reading) < flt(self.previous_reading):
            frappe.throw(
                f"Current reading ({self.current_reading}) cannot be lower than the "
                f"previous reading ({self.previous_reading})."
            )
        self.consumption = flt(self.current_reading) - flt(self.previous_reading)
        self.amount = flt(self.consumption * flt(self.rate_per_unit) + flt(self.fixed_charge), 2)

    def on_trash(self):
        self.validate_not_invoiced()

    def validate_not_invoiced(self):
        if not self.is_new() and frappe.db.get_value("Utility Reading", self.name, "status") == "Invoiced":
            frappe.throw(
                f"This reading is already on invoice <b>{self.sales_invoice}</b>. "
                f"Cancel that invoice first to change it."
            )

    def validate_unit_on_lease(self):
        if frappe.db.get_value("Lease Agreement", self.lease, "docstatus") != 1:
            frappe.throw(f"Lease Agreement <b>{self.lease}</b> must be submitted.")
        lease_units = frappe.get_all(
            "Lease Agreement Unit", filters={"parent": self.lease}, pluck="unit_id"
        )
        if self.unit not in lease_units:
            frappe.throw(
                f"Unit <b>{self.unit}</b> is not part of Lease Agreement <b>{self.lease}</b>."
            )

    @frappe.whitelist()
    def create_invoice(self):
        from pms.pms.billing import make_utility_invoice
        return make_utility_invoice([self.name])


@frappe.whitelist()
def get_previous_reading(unit, utility_type, lease=None, reading_date=None, name=None):
    """Last reading of this unit's meter before `reading_date`; failing that,
    the meter reading recorded at Move In for this lease (or the lease it
    renewed); else 0."""
    previous = frappe.get_all(
        "Utility Reading",
        filters={
            "unit": unit,
            "utility_type": utility_type,
            "name": ["!=", name or ""],
            "reading_date": ["<=", reading_date or frappe.utils.today()],
        },
        pluck="current_reading",
        order_by="reading_date desc, creation desc",
        limit=1,
    )
    if previous:
        return flt(previous[0])

    if lease:
        from pms.pms.doctype.lease_agreement.lease_agreement import get_lease_chain
        move_in = frappe.db.get_value(
            "Move In", {"lease": ["in", get_lease_chain(lease)], "unit": unit, "docstatus": 1},
            "name", order_by="creation desc",
        )
        if move_in:
            reading = frappe.db.get_value(
                "Move In Meter Reading",
                {"parent": move_in, "parenttype": "Move In", "meter_type": utility_type},
                "reading",
            )
            return flt(reading)
    return 0


@frappe.whitelist()
def get_last_rate(unit, utility_type, name=None):
    rate = frappe.get_all(
        "Utility Reading",
        filters={"unit": unit, "utility_type": utility_type, "name": ["!=", name or ""]},
        pluck="rate_per_unit",
        order_by="reading_date desc, creation desc",
        limit=1,
    )
    return flt(rate[0]) if rate else 0


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def lease_units_query(doctype, txt, searchfield, start, page_len, filters):
    """Unit picker on Utility Reading: only the units on the chosen lease."""
    return frappe.db.sql(
        """
        SELECT unit_id FROM `tabLease Agreement Unit`
        WHERE parent = %(lease)s AND parenttype = 'Lease Agreement'
          AND unit_id LIKE %(txt)s
        ORDER BY idx
        LIMIT %(start)s, %(page_len)s
        """,
        {"lease": filters.get("lease"), "txt": f"%{txt}%", "start": start, "page_len": page_len},
    )
