# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, date_diff, today

from pms.pms.billing import ensure_item


class ServiceApartmentBooking(Document):

    def validate(self):
        self.validate_dates()
        self.set_default_rate()
        self.calculate_total()
        self.validate_unit_available()

    def on_trash(self):
        if self.status == "Checked In":
            frappe.throw("Cannot delete a booking that is Checked In. Check out first.")

    # ------------------------------------------------------------
    def validate_dates(self):
        if self.check_in and self.check_out:
            if getdate(self.check_out) <= getdate(self.check_in):
                frappe.throw("Check Out must be after Check In.")
            self.no_of_nights = date_diff(
                getdate(self.check_out), getdate(self.check_in)
            )

    def set_default_rate(self):
        if not flt(self.rate_per_night) and self.unit:
            monthly = frappe.db.get_value("Asset", self.unit, "custom_monthly_rent")
            if monthly:
                self.rate_per_night = flt(monthly) / 30

    def calculate_total(self):
        base = flt(self.rate_per_night) * (self.no_of_nights or 0)
        self.total_amount = base + flt(self.extra_charges) - flt(self.discount_amount)
        if self.total_amount < 0:
            frappe.throw("Discount cannot be more than the booking amount.")

    def validate_unit_available(self):
        """No overlap with other bookings, and unit not under an active lease."""
        if not (self.unit and self.check_in and self.check_out):
            return

        # Overlapping bookings on the same unit
        overlap = frappe.db.sql("""
            SELECT name FROM `tabService Apartment Booking`
            WHERE unit = %s
              AND name != %s
              AND status IN ('Booked', 'Checked In')
              AND check_in < %s
              AND check_out > %s
            LIMIT 1
        """, (self.unit, self.name or "new", self.check_out, self.check_in))
        if overlap:
            frappe.throw(
                f"Unit <b>{self.unit}</b> already has booking "
                f"<b>{overlap[0][0]}</b> overlapping these dates."
            )

        # Unit locked by a long-term lease
        lease = frappe.db.sql("""
            SELECT la.name FROM `tabLease Agreement` la
            INNER JOIN `tabLease Agreement Unit` lau ON lau.parent = la.name
            WHERE lau.unit_id = %s
              AND la.docstatus = 1
              AND la.status = 'Active'
            LIMIT 1
        """, self.unit)
        if lease:
            frappe.throw(
                f"Unit <b>{self.unit}</b> is under active Lease Agreement "
                f"<b>{lease[0][0]}</b> and cannot be booked short-term."
            )

    # ------------------------------------------------------------
    # Status actions (called from JS buttons)
    # ------------------------------------------------------------
    @frappe.whitelist()
    def check_in_guest(self):
        if self.status != "Booked":
            frappe.throw(f"Cannot check in: booking is {self.status}.")
        occ = frappe.db.get_value("Asset", self.unit, "custom_occupancy_status")
        if occ == "Occupied":
            frappe.throw(f"Unit <b>{self.unit}</b> is currently Occupied.")

        frappe.db.set_value("Asset", self.unit, {
            "custom_occupancy_status": "Occupied",
            "custom_start_date": getdate(self.check_in),
            "custom_end_date": getdate(self.check_out),
        })
        self.db_set("status", "Checked In")
        frappe.msgprint("Guest checked in. Unit marked Occupied.",
                        indicator="green", alert=True)

    @frappe.whitelist()
    def check_out_guest(self):
        if self.status != "Checked In":
            frappe.throw(f"Cannot check out: booking is {self.status}.")

        self._release_unit()
        self.db_set("status", "Checked Out")
        frappe.msgprint("Guest checked out. Unit released.",
                        indicator="green", alert=True)

    @frappe.whitelist()
    def cancel_booking(self):
        if self.status == "Checked Out":
            frappe.throw("Booking already completed.")
        if self.status == "Checked In":
            self._release_unit()
        self.db_set("status", "Cancelled")
        frappe.msgprint("Booking cancelled.", indicator="orange", alert=True)

    @frappe.whitelist()
    def make_invoice(self):
        if self.sales_invoice:
            frappe.throw(f"Invoice <b>{self.sales_invoice}</b> already exists.")
        if not self.customer:
            frappe.throw(
                f"Guest <b>{self.guest}</b> has no linked Customer. "
                f"Open and save the Tenant once, then reload this booking."
            )

        items = [{
            "item_code": ensure_item("Service Apartment Stay"),
            "qty": self.no_of_nights or 1,
            "uom": "Nos",
            "rate": flt(self.rate_per_night),
            "asset": self.unit,
            "description": (
                f"Service apartment stay — Unit {self.unit}, "
                f"{self.check_in} to {self.check_out} "
                f"({self.no_of_nights} nights)"
            ),
        }]
        if flt(self.extra_charges):
            items.append({
                "item_code": ensure_item("PMS Additional Charges"),
                "qty": 1,
                "uom": "Nos",
                "rate": flt(self.extra_charges),
                "description": f"Extra charges — booking {self.name}",
            })

        si = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": self.customer,
            "posting_date": today(),
            "due_date": today(),
            "ignore_pricing_rule": 1,
            "items": items,
            "apply_discount_on": "Net Total",
            "discount_amount": flt(self.discount_amount),
            "remarks": f"Service Apartment Booking: {self.name}\nGuest: {self.guest}",
        })
        si.insert(ignore_permissions=True)
        self.db_set("sales_invoice", si.name)
        return si.name

    def _release_unit(self):
        if self.unit and frappe.db.exists("Asset", self.unit):
            frappe.db.set_value("Asset", self.unit, {
                "custom_occupancy_status": "Vacent",
                "custom_start_date": None,
                "custom_end_date": None,
            })
