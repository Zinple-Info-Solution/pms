# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

from pms.pms.billing import ensure_item, get_active_customer_for_unit


class MeterReading(Document):

    def validate(self):
        meter = frappe.get_doc("Utility Meter", self.meter)

        previous = frappe.db.sql(
            """
            SELECT current_reading FROM `tabMeter Reading`
            WHERE meter = %(meter)s AND name != %(name)s AND reading_date <= %(reading_date)s
            ORDER BY reading_date DESC, creation DESC
            LIMIT 1
            """,
            {"meter": self.meter, "name": self.name or "", "reading_date": self.reading_date},
        )
        self.previous_reading = flt(previous[0][0]) if previous else flt(meter.initial_reading)

        if flt(self.current_reading) < flt(self.previous_reading):
            frappe.throw(
                f"Current reading ({self.current_reading}) cannot be lower than the "
                f"previous reading ({self.previous_reading}). If this meter was replaced, "
                f"update its Initial Reading on the Utility Meter instead of backdating here."
            )

        self.consumption = flt(self.current_reading) - flt(self.previous_reading)
        self.amount = flt(self.consumption) * flt(meter.rate_per_unit) + flt(meter.fixed_monthly_charge)

    @frappe.whitelist()
    def create_invoice(self):
        """Invoice the active tenant of this meter's Unit for this reading's
        consumption. Meters with no Unit (common-area/property-level) have
        no tenant to bill — they're recorded for consumption reporting only."""
        if self.status == "Invoiced":
            frappe.throw("This reading has already been invoiced.")

        meter = frappe.get_doc("Utility Meter", self.meter)
        if not meter.unit:
            self.db_set("status", "Not Billable")
            frappe.throw(
                "This meter has no Unit assigned, so there is no tenant to invoice. "
                "Use this reading for consumption reporting only."
            )

        customer = get_active_customer_for_unit(meter.unit)
        if not customer:
            frappe.throw(f"No active tenant found for unit <b>{meter.unit}</b> to invoice.")

        cost_center = frappe.db.get_value("Property", meter.property, "cost_center")
        item_code = (
            meter.charge_type and frappe.db.get_value("Charge Type", meter.charge_type, "item")
        ) or ensure_item(f"Utility - {self.utility_type}")

        si = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": customer,
            "posting_date": today(),
            "due_date": today(),
            "ignore_pricing_rule": 1,
            "items": [{
                "item_code": item_code,
                "qty": 1,
                "uom": "Nos",
                "rate": self.amount,
                "cost_center": cost_center,
                "description": (
                    f"{self.utility_type} consumption: {self.consumption} units "
                    f"({self.previous_reading} → {self.current_reading}) for {meter.unit}"
                ),
            }],
            "remarks": f"Utility billing for Meter Reading {self.name} ({meter.name})",
        })
        si.insert(ignore_permissions=True)
        self.db_set("sales_invoice", si.name)
        self.db_set("status", "Invoiced")

        frappe.msgprint(
            f"Utility invoice <b>{si.name}</b> created.", indicator="green", alert=True
        )
        return si.name
