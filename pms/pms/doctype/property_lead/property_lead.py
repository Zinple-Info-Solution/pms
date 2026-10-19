# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class PropertyLead(Document):

    def validate(self):
        self.validate_units()

    def validate_units(self):
        if self.interested_units and not self.property:
            frappe.throw("Select a Property before choosing units.")

        for row in self.interested_units or []:
            unit_property = frappe.db.get_value("Unit", row.unit, "property")
            if unit_property != self.property:
                frappe.throw(
                    f"Unit <b>{row.unit}</b> belongs to property <b>{unit_property}</b>, "
                    f"not <b>{self.property}</b>."
                )

    def after_insert(self):
        self.send_auto_reply()

    def send_auto_reply(self):
        if not self.email:
            return
        try:
            units = ", ".join(row.unit for row in self.interested_units or [])
            interest = f"{self.property} ({units})" if units else self.property
            frappe.sendmail(
                recipients=[self.email],
                subject="Thanks for your interest!",
                message=(
                    f"<p>Hi {self.lead_name},</p>"
                    f"<p>Thanks for reaching out"
                    f"{' about ' + interest if interest else ''}. "
                    f"One of our leasing agents will contact you shortly to arrange a site visit.</p>"
                ),
                delayed=True,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Lead auto-reply failed: {self.name}")
