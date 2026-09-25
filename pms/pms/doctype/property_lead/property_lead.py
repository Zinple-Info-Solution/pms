# Copyright (c) 2026, admin and contributors
import frappe
from frappe.model.document import Document


class PropertyLead(Document):

    def after_insert(self):
        self.send_auto_reply()

    def send_auto_reply(self):
        if not self.email:
            return
        try:
            frappe.sendmail(
                recipients=[self.email],
                subject="Thanks for your interest!",
                message=(
                    f"<p>Hi {self.lead_name},</p>"
                    f"<p>Thanks for reaching out"
                    f"{' about ' + self.interested_property if self.interested_property else ''}. "
                    f"One of our leasing agents will contact you shortly to arrange a site visit.</p>"
                ),
                delayed=True,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Lead auto-reply failed: {self.name}")
