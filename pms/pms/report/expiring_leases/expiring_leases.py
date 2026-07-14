# Copyright (c) 2026, admin and contributors
import frappe
from frappe.utils import today, add_days, date_diff, getdate


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "lease",
            "label": "Lease Agreement",
            "fieldtype": "Link",
            "options": "Lease Agreement",
            "width": 180,
        },
        {
            "fieldname": "tenant",
            "label": "Tenant",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 160,
        },
        {
            "fieldname": "building",
            "label": "Building",
            "fieldtype": "Link",
            "options": "Building",
            "width": 150,
        },
        {"fieldname": "start_date", "label": "Start Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "end_date", "label": "End Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "days_remaining", "label": "Days Remaining", "fieldtype": "Int", "width": 130},
        {"fieldname": "rent_amount", "label": "Rent Amount", "fieldtype": "Currency", "width": 130},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    days_ahead = int(filters.get("days_ahead") or 60)

    conditions = {
        "docstatus": 1,
        "status": "Active",
        "end_date": ["<=", add_days(today(), days_ahead)],
    }
    if filters.get("building"):
        conditions["building"] = filters["building"]

    leases = frappe.get_all(
        "Lease Agreement",
        filters=conditions,
        fields=[
            "name", "tenant", "building", "start_date",
            "end_date", "rent_amount", "status",
        ],
        order_by="end_date asc",
    )

    data = []
    for lease in leases:
        data.append({
            "lease": lease.name,
            "tenant": lease.tenant,
            "building": lease.building,
            "start_date": lease.start_date,
            "end_date": lease.end_date,
            "days_remaining": date_diff(getdate(lease.end_date), getdate(today())),
            "rent_amount": lease.rent_amount,
            "status": lease.status,
        })

    return data
