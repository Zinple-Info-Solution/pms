# Copyright (c) 2026, admin and contributors
"""Utility Consumption: one row per Meter Reading, showing consumption and
billed amount by property/unit/utility type over a date range."""

import frappe


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "name", "label": "Meter Reading", "fieldtype": "Link",
         "options": "Meter Reading", "width": 150},
        {"fieldname": "property", "label": "Property", "fieldtype": "Link",
         "options": "Property", "width": 150},
        {"fieldname": "unit", "label": "Unit", "fieldtype": "Link",
         "options": "Unit", "width": 120},
        {"fieldname": "utility_type", "label": "Utility", "fieldtype": "Data", "width": 90},
        {"fieldname": "reading_date", "label": "Reading Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "previous_reading", "label": "Previous", "fieldtype": "Float", "width": 90},
        {"fieldname": "current_reading", "label": "Current", "fieldtype": "Float", "width": 90},
        {"fieldname": "consumption", "label": "Consumption", "fieldtype": "Float", "width": 100},
        {"fieldname": "amount", "label": "Amount", "fieldtype": "Currency", "width": 110},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 90},
    ]


def get_data(filters):
    conditions = ["1=1"]
    values = {}

    if filters.get("property"):
        conditions.append("m.property = %(property)s")
        values["property"] = filters["property"]
    if filters.get("unit"):
        conditions.append("mr.unit = %(unit)s")
        values["unit"] = filters["unit"]
    if filters.get("utility_type"):
        conditions.append("mr.utility_type = %(utility_type)s")
        values["utility_type"] = filters["utility_type"]
    if filters.get("from_date"):
        conditions.append("mr.reading_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions.append("mr.reading_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    return frappe.db.sql(
        f"""
        SELECT mr.name, m.property, mr.unit, mr.utility_type, mr.reading_date,
               mr.previous_reading, mr.current_reading, mr.consumption,
               mr.amount, mr.status
        FROM `tabMeter Reading` mr
        INNER JOIN `tabUtility Meter` m ON m.name = mr.meter
        WHERE {" AND ".join(conditions)}
        ORDER BY mr.reading_date DESC
        """,
        values,
        as_dict=True,
    )
