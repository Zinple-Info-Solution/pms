# Copyright (c) 2026, admin and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestProperty(FrappeTestCase):
	def test_sync_units_creates_unit_records(self):
		if not frappe.db.exists("Unit Type", "Test Studio Type"):
			frappe.get_doc({"doctype": "Unit Type", "unit_type": "Test Studio Type"}).insert()

		property_doc = frappe.get_doc({
			"doctype": "Property",
			"building_name": "Test Property For Units",
			"status": "Available",
			"units": [
				{"unit_type": "Test Studio Type", "floor_no": 1, "unit_no": 2, "monthly_rent": 10000},
			],
		})
		property_doc.insert()
		self.addCleanup(lambda: frappe.delete_doc("Property", property_doc.name, force=True))

		units = frappe.get_all("Unit", filters={"property": property_doc.name})
		self.assertEqual(len(units), 2)

	def test_reducing_unit_count_leaves_existing_units(self):
		if not frappe.db.exists("Unit Type", "Test Studio Type"):
			frappe.get_doc({"doctype": "Unit Type", "unit_type": "Test Studio Type"}).insert()

		property_doc = frappe.get_doc({
			"doctype": "Property",
			"building_name": "Test Property Shrink",
			"status": "Available",
			"units": [
				{"unit_type": "Test Studio Type", "floor_no": 1, "unit_no": 2, "monthly_rent": 10000},
			],
		})
		property_doc.insert()
		self.addCleanup(lambda: frappe.delete_doc("Property", property_doc.name, force=True))

		property_doc.units[0].unit_no = 1
		property_doc.save()

		units = frappe.get_all("Unit", filters={"property": property_doc.name})
		self.assertEqual(len(units), 2)
