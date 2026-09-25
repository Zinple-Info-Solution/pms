# Copyright (c) 2026, admin and contributors
import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart


def get_columns():
    return [
        {
            "fieldname": "building",
            "label": "Property",
            "fieldtype": "Link",
            "options": "Property",
            "width": 200,
        },
        {"fieldname": "total_units", "label": "Total Units", "fieldtype": "Int", "width": 110},
        {"fieldname": "occupied", "label": "Occupied", "fieldtype": "Int", "width": 100},
        {"fieldname": "vacant", "label": "Vacant", "fieldtype": "Int", "width": 100},
        {"fieldname": "occupancy_rate", "label": "Occupancy %", "fieldtype": "Percent", "width": 120},
        {
            "fieldname": "monthly_rent_potential",
            "label": "Rent Potential / Month",
            "fieldtype": "Currency",
            "width": 170,
        },
        {
            "fieldname": "monthly_rent_actual",
            "label": "Rent Collected / Month",
            "fieldtype": "Currency",
            "width": 170,
        },
    ]


def get_data(filters):
    conditions = {}
    if filters.get("building"):
        conditions["property"] = filters["building"]

    units = frappe.get_all(
        "Unit",
        filters=conditions,
        fields=[
            "property as building",
            "status",
            "monthly_rent as rent",
        ],
    )

    buildings = {}
    for a in units:
        b = buildings.setdefault(a.building or "Unknown", {
            "building": a.building or "Unknown",
            "total_units": 0,
            "occupied": 0,
            "vacant": 0,
            "monthly_rent_potential": 0,
            "monthly_rent_actual": 0,
        })
        b["total_units"] += 1
        b["monthly_rent_potential"] += a.rent or 0

        if a.status == "Occupied":
            b["occupied"] += 1
            b["monthly_rent_actual"] += a.rent or 0
        else:
            b["vacant"] += 1

    data = []
    for b in buildings.values():
        b["occupancy_rate"] = (
            (b["occupied"] / b["total_units"]) * 100 if b["total_units"] else 0
        )
        data.append(b)

    return sorted(data, key=lambda x: x["building"])


def get_chart(data):
    if not data:
        return None
    return {
        "data": {
            "labels": [d["building"] for d in data],
            "datasets": [
                {"name": "Occupied", "values": [d["occupied"] for d in data]},
                {"name": "Vacant", "values": [d["vacant"] for d in data]},
            ],
        },
        "type": "bar",
        "colors": ["#28a745", "#ff9800"],
    }
